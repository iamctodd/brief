#!/usr/bin/env python3
"""
Morning Information Diet Agent - Version 3
Web dashboard + personalization + analytics.

New concepts:
- Web framework (Flask) for UI
- Database for user preferences and history
- Analytics to learn what users find valuable
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)

class UserPreferences:
    """Manage user settings in SQLite."""
    
    def __init__(self, db_path="morning_agent.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Users and their preferences
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE,
            topics TEXT,  -- JSON array
            schedule_time TEXT,
            positivity_threshold REAL,
            created_at TIMESTAMP
        )''')
        
        # Track which briefs were sent and engaged
        c.execute('''CREATE TABLE IF NOT EXISTS brief_history (
            id INTEGER PRIMARY KEY,
            user_email TEXT,
            date DATE,
            articles_shown INTEGER,
            articles_clicked INTEGER,
            opened BOOLEAN,
            opened_at TIMESTAMP,
            created_at TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()
    
    def get_user(self, email: str) -> dict:
        """Retrieve user preferences."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {
                "email": row[1],
                "topics": json.loads(row[2]),
                "schedule_time": row[3],
                "positivity_threshold": row[4]
            }
        return None
    
    def create_user(self, email: str, topics: list, schedule_time: str, threshold: float):
        """Create new user preferences."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''INSERT INTO users (email, topics, schedule_time, positivity_threshold, created_at)
                     VALUES (?, ?, ?, ?, ?)''',
                  (email, json.dumps(topics), schedule_time, threshold, datetime.now()))
        
        conn.commit()
        conn.close()
    
    def log_brief_sent(self, email: str, articles_shown: int):
        """Log when a brief is sent."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''INSERT INTO brief_history (user_email, date, articles_shown, opened, created_at)
                     VALUES (?, ?, ?, ?, ?)''',
                  (email, datetime.now().date(), articles_shown, False, datetime.now()))
        
        conn.commit()
        conn.close()
    
    def log_brief_opened(self, email: str):
        """Track when a user opens their brief (via email tracking pixel)."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''UPDATE brief_history 
                     SET opened = 1, opened_at = ?
                     WHERE user_email = ? AND date = ?''',
                  (datetime.now(), email, datetime.now().date()))
        
        conn.commit()
        conn.close()
    
    def get_engagement_stats(self, email: str, days: int = 30) -> dict:
        """Get user engagement statistics."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Days delivered
        c.execute('''SELECT COUNT(*) FROM brief_history 
                     WHERE user_email = ? AND date >= date('now', ?)''',
                  (email, f'-{days} days'))
        total_sent = c.fetchone()[0]
        
        # Days opened
        c.execute('''SELECT COUNT(*) FROM brief_history 
                     WHERE user_email = ? AND opened = 1 AND date >= date('now', ?)''',
                  (email, f'-{days} days'))
        total_opened = c.fetchone()[0]
        
        conn.close()
        
        return {
            "days_in_period": days,
            "briefs_delivered": total_sent,
            "briefs_opened": total_opened,
            "open_rate": (total_opened / total_sent * 100) if total_sent > 0 else 0
        }


# Initialize database
prefs = UserPreferences()


@app.route("/")
def dashboard():
    """Main dashboard view."""
    return """
    <html>
    <head>
        <title>☀️ Morning Information Diet</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f9fafb; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }
            .header h1 { margin: 0; }
            .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
            .input-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: 500; }
            input, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
            button { background: #667eea; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; }
            button:hover { background: #5568d3; }
            .stat { display: inline-block; margin-right: 30px; }
            .stat-value { font-size: 24px; font-weight: bold; color: #667eea; }
            .stat-label { font-size: 12px; color: #999; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>☀️ Your Morning Information Diet</h1>
            <p>Quality over quantity. A better way to start your day.</p>
        </div>
        
        <div class="card">
            <h2>Setup Your Preferences</h2>
            <div class="input-group">
                <label>Email Address</label>
                <input type="email" id="email" placeholder="you@example.com">
            </div>
            <div class="input-group">
                <label>Topics to Follow (comma-separated)</label>
                <input type="text" id="topics" placeholder="e.g., artificial intelligence, climate tech, startups">
            </div>
            <div class="input-group">
                <label>Morning Brief Time</label>
                <input type="time" id="schedule_time" value="07:30">
            </div>
            <div class="input-group">
                <label>Positivity Filter (0=all news, 1=ultra-positive only)</label>
                <input type="range" id="threshold" min="0" max="1" step="0.1" value="0.4">
                <span id="threshold_display">0.4</span>
            </div>
            <button onclick="savePreferences()">Save Preferences</button>
        </div>
        
        <div class="card">
            <h2>📊 Your Engagement</h2>
            <div id="stats">Loading...</div>
        </div>
        
        <script>
            document.getElementById('threshold').addEventListener('input', (e) => {
                document.getElementById('threshold_display').textContent = e.target.value;
            });
            
            function savePreferences() {
                const data = {
                    email: document.getElementById('email').value,
                    topics: document.getElementById('topics').value.split(',').map(t => t.trim()),
                    schedule_time: document.getElementById('schedule_time').value,
                    positivity_threshold: parseFloat(document.getElementById('threshold').value)
                };
                
                fetch('/api/preferences', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                })
                .then(r => r.json())
                .then(d => alert(d.message))
                .catch(e => alert('Error: ' + e));
            }
            
            function loadStats() {
                const email = document.getElementById('email').value;
                if (!email) return;
                
                fetch('/api/stats?email=' + email)
                    .then(r => r.json())
                    .then(d => {
                        document.getElementById('stats').innerHTML = `
                            <div class="stat">
                                <div class="stat-value">${d.briefs_delivered}</div>
                                <div class="stat-label">Briefs Delivered (30d)</div>
                            </div>
                            <div class="stat">
                                <div class="stat-value">${d.briefs_opened}</div>
                                <div class="stat-label">Opened</div>
                            </div>
                            <div class="stat">
                                <div class="stat-value">${d.open_rate.toFixed(0)}%</div>
                                <div class="stat-label">Open Rate</div>
                            </div>
                        `;
                    });
            }
            
            document.getElementById('email').addEventListener('blur', loadStats);
        </script>
    </body>
    </html>
    """


@app.route("/api/preferences", methods=["POST"])
def set_preferences():
    """API endpoint to save user preferences."""
    data = request.json
    
    try:
        existing = prefs.get_user(data["email"])
        if existing:
            # Update logic would go here
            message = "Preferences updated"
        else:
            prefs.create_user(
                data["email"],
                data["topics"],
                data["schedule_time"],
                data["positivity_threshold"]
            )
            message = "Profile created! Your first brief will arrive at " + data["schedule_time"]
        
        return jsonify({"success": True, "message": message})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """API endpoint to get engagement stats."""
    email = request.args.get("email")
    if not email:
        return {"error": "No email provided"}, 400
    
    stats = prefs.get_engagement_stats(email)
    return jsonify(stats)


@app.route("/pixel/<email>")
def tracking_pixel(email):
    """Invisible pixel to track email opens."""
    prefs.log_brief_opened(email)
    # Return a 1x1 transparent GIF
    gif = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xFF\xFF\xFF\x21\xF9\x04\x01\x00\x00\x00\x00\x2C\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3B'
    return gif, 200, {"Content-Type": "image/gif"}


if __name__ == "__main__":
    print("🚀 Starting Morning Agent Dashboard")
    print("   Open: http://localhost:5000")
    app.run(debug=True)