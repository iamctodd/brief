#!/usr/bin/env python3
from flask import Flask, request, jsonify
import os
import markdown2
import requests
from anthropic import Anthropic
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
client = None

def get_client():
    global client
    if client is None:
        saved = {}
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']:
            if key in os.environ:
                saved[key] = os.environ.pop(key)
        try:
            client = Anthropic()
        finally:
            for key, val in saved.items():
                os.environ[key] = val
    return client

current_briefs = {}
current_briefs_html = ""

TOPICS = {
    "business markets": {"label": "Business & Markets", "icon": "📊"},
    "space science": {"label": "Space & Science", "icon": "🚀"},
    "cybersecurity": {"label": "Cybersecurity", "icon": "🔒"},
    "artificial intelligence": {"label": "Artificial Intelligence", "icon": "🤖"},
    "climate technology": {"label": "Climate Technology", "icon": "🌍"},
    "renewable energy": {"label": "Renewable Energy", "icon": "⚡"},
    "health wellness": {"label": "Health & Wellness", "icon": "❤️"},
    "music entertainment": {"label": "Music & Entertainment", "icon": "🎵"}
}

def fetch_articles(topics: list) -> dict:
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return {}
    
    url = "https://newsapi.org/v2/everything"
    articles_by_topic = {}
    
    for topic in topics:
        try:
            response = requests.get(url, params={
                "q": topic,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": 5,
                "apiKey": api_key
            }, timeout=10)
            
            data = response.json()
            if data.get("status") == "ok":
                articles_by_topic[topic] = [
                    {
                        "title": a["title"],
                        "description": a["description"],
                        "url": a["url"],
                        "source": a["source"]["name"],
                        "published": a["publishedAt"][:10]
                    }
                    for a in data.get("articles", [])
                ]
            else:
                articles_by_topic[topic] = []
        except Exception as e:
            print(f"Error fetching {topic}: {e}")
            articles_by_topic[topic] = []
    
    return articles_by_topic

def synthesize_brief(topic: str, articles: list) -> str:
    if not articles:
        return f"No articles found about {topic}."
    
    articles_text = "\n".join([
        f"- {a['title']}\n  {a['description']}"
        for a in articles
    ])
    
    message = get_client().messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""Synthesize this news about {topic} into a SHORT (2-3 sentences), POSITIVE morning brief that can be read in 5 minutes.

Focus on opportunities and progress. End with "Today's focus:" and one actionable insight. Keep it under 150 words.

Articles:
{articles_text}

Write the brief:"""
        }]
    )
    
    return message.content[0].text

@app.route("/")
def index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AM Brief - Your Morning Information Diet</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body.light {
            --bg: #ffffff;
            --bg-secondary: #f8f8f8;
            --text: #222222;
            --text-secondary: #666666;
            --border: #e0e0e0;
            --accent: #0066cc;
            --card-bg: #ffffff;
        }
        
        body.dark {
            --bg: #0f0f0f;
            --bg-secondary: #1a1a1a;
            --text: #ffffff;
            --text-secondary: #aaaaaa;
            --border: #333333;
            --accent: #4a9eff;
            --card-bg: #1a1a1a;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            transition: background 0.3s, color 0.3s;
        }
        
        .container { max-width: 900px; margin: 0 auto; padding: 60px 24px; }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 60px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }
        
        .logo { font-size: 24px; font-weight: 700; }
        
        .theme-toggle {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            padding: 8px;
            border-radius: 8px;
            transition: background 0.2s;
        }
        
        .theme-toggle:hover { background: var(--bg-secondary); }
        
        .wizard-steps {
            display: flex;
            justify-content: space-between;
            margin-bottom: 60px;
        }
        
        .step {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
            opacity: 0.5;
            transition: opacity 0.3s;
        }
        
        .step.active { opacity: 1; }
        
        .step-number {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--bg-secondary);
            border: 2px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
        }
        
        .step.active .step-number {
            background: var(--accent);
            color: white;
            border-color: var(--accent);
        }
        
        .step-label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        
        .wizard-content { margin-bottom: 60px; }
        
        .step-content { display: none; }
        .step-content.active { display: block; }
        
        .step-title { font-size: 32px; font-weight: 700; margin-bottom: 12px; }
        .step-subtitle { font-size: 16px; color: var(--text-secondary); margin-bottom: 40px; }
        
        .topics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 40px;
        }
        
        .topic-card {
            padding: 16px;
            border: 2px solid var(--border);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            background: var(--card-bg);
        }
        
        .topic-card:hover { border-color: var(--accent); }
        
        .topic-card input[type="checkbox"] {
            cursor: pointer;
            width: 18px;
            height: 18px;
            accent-color: var(--accent);
            margin-right: 12px;
        }
        
        .topic-card label {
            cursor: pointer;
            display: flex;
            align-items: center;
            font-weight: 500;
        }
        
        .topic-icon { font-size: 20px; margin-right: 8px; }
        
        textarea {
            width: 100%;
            padding: 16px;
            border: 2px solid var(--border);
            border-radius: 8px;
            background: var(--card-bg);
            color: var(--text);
            font-size: 14px;
            font-family: inherit;
            min-height: 100px;
            resize: vertical;
            margin-bottom: 24px;
        }
        
        textarea:focus { outline: none; border-color: var(--accent); }
        
        .form-group {
            margin-bottom: 32px;
        }
        
        .form-label { display: block; font-weight: 600; margin-bottom: 12px; }
        
        input[type="email"], input[type="time"] {
            width: 100%;
            padding: 12px;
            border: 2px solid var(--border);
            border-radius: 8px;
            background: var(--card-bg);
            color: var(--text);
            font-size: 14px;
            margin-bottom: 16px;
        }
        
        input[type="email"]:focus, input[type="time"]:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
        }
        
        .checkbox-group input[type="checkbox"] { cursor: pointer; }
        
        .preview-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 32px;
            margin-bottom: 32px;
        }
        
        .preview-title { font-size: 24px; font-weight: 700; margin-bottom: 16px; }
        
        .preview-brief { line-height: 1.8; margin-bottom: 24px; }
        
        .button-group {
            display: flex;
            gap: 16px;
            margin-top: 40px;
        }
        
        button {
            flex: 1;
            padding: 14px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: var(--accent);
            color: white;
        }
        
        .btn-primary:hover { opacity: 0.9; }
        
        .btn-secondary {
            background: var(--bg-secondary);
            color: var(--text);
            border: 2px solid var(--border);
        }
        
        .btn-secondary:hover { border-color: var(--accent); }
        
        .loading { text-align: center; padding: 40px; }
        .spinner {
            display: inline-block;
            width: 24px;
            height: 24px;
            border: 3px solid var(--bg-secondary);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .brief-result { margin-top: 40px; }
        
        @media (max-width: 768px) {
            .container { padding: 40px 16px; }
            .topics-grid { grid-template-columns: 1fr; }
            .button-group { flex-direction: column; }
        }
    </style>
</head>
<body class="light">
    <div class="container">
        <div class="header">
            <div class="logo">☀️ AM Brief</div>
            <button class="theme-toggle" onclick="toggleTheme()">🌙</button>
        </div>
        
        <div class="wizard-steps">
            <div class="step active" id="step-indicator-1">
                <div class="step-number">1</div>
                <div class="step-label">Choose Topics</div>
            </div>
            <div class="step" id="step-indicator-2">
                <div class="step-number">2</div>
                <div class="step-label">Add Details</div>
            </div>
            <div class="step" id="step-indicator-3">
                <div class="step-number">3</div>
                <div class="step-label">Preview</div>
            </div>
            <div class="step" id="step-indicator-4">
                <div class="step-number">4</div>
                <div class="step-label">Get Brief</div>
            </div>
        </div>
        
        <div class="wizard-content">
            <!-- Step 1: Choose Topics -->
            <div class="step-content active" id="step-1">
                <div class="step-title">What matters to you?</div>
                <div class="step-subtitle">Select the topics you care about most. We'll curate your brief around them.</div>
                
                <div class="form-group">
                    <label class="form-label">Popular Topics</label>
                    <div class="topics-grid">
                        <div class="topic-card">
                            <label>
                                <input type="checkbox" name="topics" value="business markets" class="topic-checkbox">
                                <span class="topic-icon">📊</span>
                                <span>Business & Markets</span>
                            </label>
                        </div>
                        <div class="topic-card">
                            <label>
                                <input type="checkbox" name="topics" value="space science" class="topic-checkbox">
                                <span class="topic-icon">🚀</span>
                                <span>Space & Science</span>
                            </label>
                        </div>
                        <div class="topic-card">
                            <label>
                                <input type="checkbox" name="topics" value="cybersecurity" class="topic-checkbox">
                                <span class="topic-icon">🔒</span>
                                <span>Cybersecurity</span>
                            </label>
                        </div>
                        <div class="topic-card">
                            <label>
                                <input type="checkbox" name="topics" value="artificial intelligence" class="topic-checkbox" checked>
                                <span class="topic-icon">🤖</span>
                                <span>Artificial Intelligence</span>
                            </label>
                        </div>
                        <div class="topic-card">
                            <label>
                                <input type="checkbox" name="topics" value="climate technology" class="topic-checkbox" checked>
                                <span class="topic-icon">🌍</span>
                                <span>Climate Technology</span>
                            </label>
                        </div>
                        <div class="topic-card">
                            <label>
                                <input type="checkbox" name="topics" value="renewable energy" class="topic-checkbox" checked>
                                <span class="topic-icon">⚡</span>
                                <span>Renewable Energy</span>
                            </label>
                        </div>
                        <div class="topic-card">
                            <label>
                                <input type="checkbox" name="topics" value="health wellness" class="topic-checkbox">
                                <span class="topic-icon">❤️</span>
                                <span>Health & Wellness</span>
                            </label>
                        </div>
                        <div class="topic-card">
                            <label>
                                <input type="checkbox" name="topics" value="music entertainment" class="topic-checkbox">
                                <span class="topic-icon">🎵</span>
                                <span>Music & Entertainment</span>
                            </label>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Add Custom Topics</label>
                    <textarea id="custom-topics" placeholder="Comma-separated. Example: startups, biotech, space"></textarea>
                </div>
                
                <div class="button-group">
                    <button class="btn-primary" onclick="nextStep()">Continue →</button>
                </div>
            </div>
            
            <!-- Step 2: Add Details -->
            <div class="step-content" id="step-2">
                <div class="step-title">Your preferences</div>
                <div class="step-subtitle">Tell us how you like to receive your brief.</div>
                
                <div class="form-group">
                    <label class="form-label">Email Address</label>
                    <input type="email" id="email" placeholder="your@email.com" required>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Preferred Time</label>
                    <input type="time" id="time" value="07:00">
                </div>
                
                <div class="form-group">
                    <div class="checkbox-group">
                        <input type="checkbox" id="save-prefs" checked>
                        <label for="save-prefs">Save these preferences for next time</label>
                    </div>
                </div>
                
                <div class="button-group">
                    <button class="btn-secondary" onclick="prevStep()">← Back</button>
                    <button class="btn-primary" onclick="generatePreview()">Continue →</button>
                </div>
            </div>
            
            <!-- Step 3: Preview -->
            <div class="step-content" id="step-3">
                <div class="step-title">Here's what you'll get</div>
                <div class="step-subtitle">This is a preview of your personalized morning brief.</div>
                
                <div id="preview-container" class="preview-card">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p style="margin-top: 16px;">Generating your preview...</p>
                    </div>
                </div>
                
                <div class="button-group">
                    <button class="btn-secondary" onclick="prevStep()">← Back</button>
                    <button class="btn-primary" onclick="sendBrief()">Get My Brief →</button>
                </div>
            </div>
            
            <!-- Step 4: Get Brief -->
            <div class="step-content" id="step-4">
                <div class="step-title">Your Morning Brief</div>
                <div id="brief-result" class="brief-result"></div>
            </div>
        </div>
    </div>
    
    <script>
        let currentStep = 1;
        let previewHtml = '';
        
        function toggleTheme() {
            document.body.classList.toggle('dark');
            localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
            updateThemeButton();
        }
        
        function updateThemeButton() {
            document.querySelector('.theme-toggle').textContent = document.body.classList.contains('dark') ? '☀️' : '🌙';
        }
        
        // Load theme preference
        if (localStorage.getItem('theme') === 'dark') {
            document.body.classList.add('dark');
            updateThemeButton();
        }
        
        function goToStep(step) {
            document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.step').forEach(el => el.classList.remove('active'));
            
            document.getElementById('step-' + step).classList.add('active');
            document.getElementById('step-indicator-' + step).classList.add('active');
            
            currentStep = step;
            window.scrollTo(0, 0);
        }
        
        function nextStep() {
            const topics = Array.from(document.querySelectorAll('input[name="topics"]:checked')).map(el => el.value);
            const custom = document.getElementById('custom-topics').value.split(',').map(t => t.trim()).filter(t => t);
            const allTopics = [...topics, ...custom];
            
            if (!allTopics.length) {
                alert('Please select at least one topic');
                return;
            }
            
            localStorage.setItem('selected-topics', JSON.stringify(allTopics));
            goToStep(2);
        }
        
        function prevStep() {
            if (currentStep > 1) goToStep(currentStep - 1);
        }
        
        async function generatePreview() {
            const email = document.getElementById('email').value;
            const time = document.getElementById('time').value;
            
            if (!email) {
                alert('Please enter your email');
                return;
            }
            
            localStorage.setItem('email', email);
            localStorage.setItem('time', time);
            
            if (document.getElementById('save-prefs').checked) {
                localStorage.setItem('preferences-saved', 'true');
            }
            
            goToStep(3);
            
            const topics = JSON.parse(localStorage.getItem('selected-topics') || '[]');
            
            try {
                const res = await fetch('/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({topics})
                });
                
                if (!res.ok) throw new Error('Failed to generate');
                
                const html = await res.text();
                
                // Store the full HTML for later
                localStorage.setItem('brief-html', html);
                
                // Extract just the briefs content for preview
                const startMarker = '<!-- BRIEFS_START -->';
                const endMarker = '<!-- BRIEFS_END -->';
                const startIdx = html.indexOf(startMarker);
                const endIdx = html.indexOf(endMarker);
                
                if (startIdx !== -1 && endIdx !== -1) {
                    const briefsContent = html.substring(startIdx + startMarker.length, endIdx);
                    document.getElementById('preview-container').innerHTML = briefsContent;
                } else {
                    document.getElementById('preview-container').innerHTML = '<p>Brief generated successfully!</p>';
                }
            } catch (e) {
                console.error('Error:', e);
                document.getElementById('preview-container').innerHTML = '<p style="color: red;">Error generating preview: ' + e.message + '</p>';
            }
        }
        
        async function sendBrief() {
            goToStep(4);
            
            const email = localStorage.getItem('email');
            const briefHtml = localStorage.getItem('brief-html');
            
            try {
                const res = await fetch('/send-email', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email})
                });
                
                const data = await res.json();
                
                if (data.success) {
                    // Show the stored brief
                    if (briefHtml) {
                        document.getElementById('brief-result').innerHTML = briefHtml;
                    }
                    
                    // Show success message at top
                    const successMsg = '<div style="background: #e6f4ea; color: #137333; padding: 16px; border-radius: 8px; margin-bottom: 32px; border: 1px solid #81c995;">✓ Brief sent to ' + email + '! Check your inbox.</div>';
                    document.getElementById('brief-result').insertAdjacentHTML('afterbegin', successMsg);
                } else {
                    document.getElementById('brief-result').innerHTML = '<p style="color: red;">Error: ' + data.error + '</p>';
                }
            } catch (e) {
                console.error('Error:', e);
                document.getElementById('brief-result').innerHTML = '<p style="color: red;">Error sending brief: ' + e.message + '</p>';
            }
        }
        
        // Load saved preferences
        if (localStorage.getItem('preferences-saved')) {
            const saved = {
                email: localStorage.getItem('email'),
                time: localStorage.getItem('time'),
                topics: JSON.parse(localStorage.getItem('selected-topics') || '[]')
            };
            
            if (saved.email) document.getElementById('email').value = saved.email;
            if (saved.time) document.getElementById('time').value = saved.time;
            
            saved.topics.forEach(topic => {
                const checkbox = document.querySelector('input[value="' + topic + '"]');
                if (checkbox) checkbox.checked = true;
            });
        }
    </script>
</body>
</html>"""

@app.route("/generate", methods=["POST"])
def generate():
    topics = request.json.get("topics", [])
    if not topics:
        return jsonify({"error": "No topics"}), 400
    
    articles_by_topic = fetch_articles(topics)
    global current_briefs, current_briefs_html
    current_briefs = articles_by_topic
    
    briefs_html = ""
    for topic in topics:
        articles = articles_by_topic.get(topic, [])
        if articles:
            brief_text = synthesize_brief(topic, articles)
            brief_html = markdown2.markdown(brief_text, extras=['nl2br'])
            
            articles_html = "\n".join([
                f"""<article style="border: 1px solid var(--border); border-radius: 8px; padding: 24px; margin-bottom: 20px; background: var(--card-bg);">
                    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 12px;">{a['source']}</div>
                    <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 12px;"><a href="{a['url']}" target="_blank" style="color: var(--accent); text-decoration: none;">{a['title']}</a></h3>
                    <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 16px;">{a['description']}</p>
                    <time style="font-size: 12px; color: var(--text-secondary);">{a['published']}</time>
                </article>"""
                for a in articles[:3]
            ])
            
            briefs_html += f"""
            <div style="margin-bottom: 80px;">
                <h2 style="font-size: 32px; font-weight: 700; margin-bottom: 32px;">{topic.title()}</h2>
                <div style="background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 8px; padding: 32px; margin-bottom: 40px;">
                    {brief_html}
                </div>
                <h3 style="font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: var(--text-secondary); margin-bottom: 24px;">Today's Top Stories</h3>
                {articles_html}
            </div>
            """
    
    current_briefs_html = briefs_html
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Your Morning Brief</title><style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body.light {{ --bg: #ffffff; --bg-secondary: #f8f8f8; --text: #222222; --text-secondary: #666666; --border: #e0e0e0; --accent: #0066cc; --card-bg: #ffffff; }}
body.dark {{ --bg: #0f0f0f; --bg-secondary: #1a1a1a; --text: #ffffff; --text-secondary: #aaaaaa; --border: #333333; --accent: #4a9eff; --card-bg: #1a1a1a; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; transition: background 0.3s, color 0.3s; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 60px 24px; }}
.header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 60px; padding-bottom: 24px; border-bottom: 1px solid var(--border); }}
.logo {{ font-size: 24px; font-weight: 700; }}
.theme-toggle {{ background: none; border: none; font-size: 24px; cursor: pointer; padding: 8px; border-radius: 8px; transition: background 0.2s; }}
.theme-toggle:hover {{ background: var(--bg-secondary); }}
</style></head><body class="light"><div class="container"><div class="header"><div class="logo">☀️ AM Brief</div><button class="theme-toggle" onclick="toggleTheme()">🌙</button></div><!-- BRIEFS_START -->{briefs_html}<!-- BRIEFS_END --></div><script>
function toggleTheme() {{
    document.body.classList.toggle('dark');
    localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
    document.querySelector('.theme-toggle').textContent = document.body.classList.contains('dark') ? '☀️' : '🌙';
}}
if (localStorage.getItem('theme') === 'dark') {{
    document.body.classList.add('dark');
    document.querySelector('.theme-toggle').textContent = '☀️';
}}
</script></body></html>"""
    
    return html, 200, {"Content-Type": "text/html"}

@app.route("/send-email", methods=["POST"])
def send_email():
    email = request.json.get("email")
    
    if not email:
        return jsonify({"success": False, "error": "No email"}), 400
    
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    
    if not sender_email or not sender_password:
        return jsonify({"success": True, "message": "Demo mode"})
    
    try:
        briefs_html = current_briefs_html
        
        email_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: #ffffff; color: #222222; line-height: 1.6; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 60px 24px; }}
.header {{ text-align: center; margin-bottom: 60px; padding-bottom: 24px; border-bottom: 1px solid #e0e0e0; }}
.logo {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; }}
.tagline {{ font-size: 16px; color: #666666; }}
</style></head><body><div class="container"><div class="header"><div class="logo">☀️ AM Brief</div><div class="tagline">Your morning information diet</div></div>{briefs_html}</div></body></html>"""
        
        message = MIMEMultipart("alternative")
        message["Subject"] = "Your Morning Brief"
        message["From"] = sender_email
        message["To"] = email
        message.attach(MIMEText(email_html, "html"))
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, message.as_string())
        
        return jsonify({"success": True, "message": "Sent!"})
    except Exception as e:
        print(f"Email error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    print("🚀 AM Brief - Redesigned Version")
    print("   Open: http://localhost:5000")
    app.run(debug=True)