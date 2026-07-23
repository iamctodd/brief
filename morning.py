#!/usr/bin/env python3
"""
Morning Brief Web App - REDESIGNED
A simple webpage where users select topics, generate briefs, and email them.
Features a modern, clean design inspired by Google News, HN, and Flipboard.

Run: python morning_redesigned.py
Then open: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify
import os
import markdown2
import requests
import json
from anthropic import Anthropic
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

# Initialize Claude client (lazy - created when first needed)
client = None

def get_client():
    global client
    if client is None:
        client = Anthropic()
    return client

# Store generated briefs in memory (for this request cycle)
current_briefs = {}


def fetch_articles(topics: list, max_per_topic: int = 5) -> dict:
    """
    Fetch articles for multiple topics.
    
    Returns: {
        "climate tech": [article1, article2, ...],
        "ai": [article1, article2, ...],
        ...
    }
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return {"error": "NEWS_API_KEY not set"}
    
    url = "https://newsapi.org/v2/everything"
    articles_by_topic = {}
    
    for topic in topics:
        params = {
            "q": topic,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": max_per_topic,
            "apiKey": api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") == "ok":
                articles = data.get("articles", [])
                articles_by_topic[topic] = [
                    {
                        "title": a["title"],
                        "description": a["description"],
                        "url": a["url"],
                        "source": a["source"]["name"],
                        "published": a["publishedAt"][:10]
                    }
                    for a in articles
                ]
            else:
                articles_by_topic[topic] = []
        except Exception as e:
            print(f"Error fetching {topic}: {e}")
            articles_by_topic[topic] = []
    
    return articles_by_topic


def synthesize_brief(topic: str, articles: list) -> str:
    """Use Claude to create a brief from articles."""
    
    if not articles:
        return f"No articles found about {topic} today."
    
    articles_text = "\n".join([
        f"- {a['title']}\n  {a['description']}"
        for a in articles
    ])
    
    prompt = f"""You are a morning news curator. Synthesize this news about {topic} 
into a SHORT (2-3 sentences), POSITIVE, ACTIONABLE morning brief.

Rules:
- Focus on opportunities and progress, not crises
- Make it interesting
- End with "Today's focus: [actionable insight]"
- Under 150 words

Articles:
{articles_text}

Write the brief:"""
    
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text


def generate_html_brief(topics_and_articles: dict) -> str:
    """Generate a modern, clean HTML page with all briefs."""
    
    briefs_html = ""
    
    for topic, articles in topics_and_articles.items():
        if articles:
            brief_text = synthesize_brief(topic, articles)
            brief_html = markdown2.markdown(brief_text, extras=['nl2br'])
            
            articles_html = "\n".join([
                f"""
                <div class="article-card">
                    <div class="article-source">{a['source']}</div>
                    <a href="{a['url']}" target="_blank" class="article-title">{a['title']}</a>
                    <p class="article-description">{a['description']}</p>
                    <div class="article-meta">{a['published']}</div>
                </div>
                """
                for a in articles[:3]
            ])
            
            briefs_html += f"""
            <section class="brief-section">
                <div class="section-header">
                    <h2>{topic.title()}</h2>
                </div>
                <div class="brief-box">
                    {brief_html}
                </div>
                <div class="articles-section">
                    <h3>Top Stories</h3>
                    <div class="articles-grid">
                        {articles_html}
                    </div>
                </div>
            </section>
            """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>☀️ Your Morning Brief</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            
            html, body {{ height: 100%; }}
            
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif;
                background: #fafbfc;
                color: #1a1a1a;
                line-height: 1.6;
            }}
            
            .container {{
                max-width: 900px;
                margin: 0 auto;
                padding: 24px;
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 48px;
                padding-bottom: 32px;
                border-bottom: 1px solid #e5e7eb;
            }}
            
            .header h1 {{
                font-size: 42px;
                font-weight: 700;
                margin-bottom: 8px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
            
            .header p {{
                font-size: 16px;
                color: #6b7280;
            }}
            
            .brief-section {{
                margin-bottom: 56px;
            }}
            
            .section-header {{
                margin-bottom: 24px;
                padding-bottom: 12px;
                border-bottom: 2px solid #667eea;
            }}
            
            .section-header h2 {{
                font-size: 28px;
                font-weight: 600;
                color: #1a1a1a;
                letter-spacing: -0.5px;
            }}
            
            .brief-box {{
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 28px;
                margin-bottom: 28px;
                line-height: 1.8;
                font-size: 16px;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
                transition: box-shadow 0.3s ease;
            }}
            
            .brief-box:hover {{
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            }}
            
            .brief-box strong {{
                color: #667eea;
                font-weight: 600;
            }}
            
            .brief-box em {{
                color: #764ba2;
                font-style: italic;
            }}
            
            .brief-box br {{ margin: 12px 0; }}
            
            .articles-section h3 {{
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 18px;
                color: #374151;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-size: 12px;
            }}
            
            .articles-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 16px;
                margin-bottom: 32px;
            }}
            
            .article-card {{
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 20px;
                transition: all 0.3s ease;
                display: flex;
                flex-direction: column;
                height: 100%;
            }}
            
            .article-card:hover {{
                border-color: #667eea;
                box-shadow: 0 8px 24px rgba(102, 126, 234, 0.12);
                transform: translateY(-4px);
            }}
            
            .article-source {{
                display: inline-block;
                font-size: 11px;
                font-weight: 600;
                color: #667eea;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 12px;
                background: #f3f4f6;
                padding: 4px 8px;
                border-radius: 4px;
                width: fit-content;
            }}
            
            .article-title {{
                font-size: 16px;
                font-weight: 600;
                line-height: 1.4;
                margin-bottom: 12px;
                color: #1a1a1a;
                text-decoration: none;
                display: block;
                transition: color 0.2s;
            }}
            
            .article-title:hover {{
                color: #667eea;
                text-decoration: underline;
            }}
            
            .article-description {{
                font-size: 14px;
                color: #6b7280;
                line-height: 1.6;
                margin-bottom: 16px;
                flex-grow: 1;
            }}
            
            .article-meta {{
                font-size: 12px;
                color: #9ca3af;
            }}
            
            .email-section {{
                background: white;
                border: 2px solid #667eea;
                border-radius: 12px;
                padding: 32px;
                margin-top: 48px;
                text-align: center;
            }}
            
            .email-section h3 {{
                font-size: 20px;
                font-weight: 600;
                margin-bottom: 16px;
                color: #1a1a1a;
            }}
            
            .email-section p {{
                font-size: 14px;
                color: #6b7280;
                margin-bottom: 20px;
            }}
            
            .email-input {{
                width: 100%;
                max-width: 400px;
                padding: 14px 16px;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                font-size: 14px;
                margin-bottom: 16px;
                transition: border-color 0.2s;
            }}
            
            .email-input:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            
            .email-button {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 14px 32px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 600;
                font-size: 15px;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            
            .email-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
            }}
            
            .email-button:disabled {{
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }}
            
            .message {{
                padding: 14px 16px;
                border-radius: 8px;
                margin-bottom: 16px;
                display: none;
                font-size: 14px;
                font-weight: 500;
            }}
            
            .message.success {{
                background: #ecfdf5;
                color: #065f46;
                border: 1px solid #86efac;
            }}
            
            .message.error {{
                background: #fef2f2;
                color: #991b1b;
                border: 1px solid #fca5a5;
            }}
            
            .message.show {{
                display: block;
            }}
            
            .footer {{
                text-align: center;
                margin-top: 48px;
                padding-top: 24px;
                border-top: 1px solid #e5e7eb;
                font-size: 14px;
                color: #9ca3af;
            }}
            
            .footer a {{
                color: #667eea;
                text-decoration: none;
                font-weight: 500;
            }}
            
            .footer a:hover {{
                text-decoration: underline;
            }}
            
            @media (max-width: 768px) {{
                .container {{ padding: 16px; }}
                .header h1 {{ font-size: 32px; }}
                .section-header h2 {{ font-size: 24px; }}
                .brief-box {{ padding: 20px; }}
                .articles-grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>☀️ Your Morning Brief</h1>
                <p>Curated, constructive news to start your day</p>
            </div>
            
            {briefs_html}
            
            <div class="email-section">
                <h3>📧 Get This in Your Inbox</h3>
                <p>Receive briefs like this every morning</p>
                <div id="message" class="message"></div>
                <input 
                    type="email" 
                    id="emailInput" 
                    class="email-input" 
                    placeholder="your@email.com" 
                    required
                >
                <button id="sendButton" class="email-button" onclick="sendEmail()">
                    Send to My Email
                </button>
            </div>
            
            <div class="footer">
                <p><a href="/">← Back to Select Topics</a></p>
            </div>
        </div>
        
        <script>
            async function sendEmail() {{
                const email = document.getElementById('emailInput').value;
                const messageEl = document.getElementById('message');
                const button = document.getElementById('sendButton');
                
                if (!email) {{
                    messageEl.textContent = 'Please enter an email address';
                    messageEl.className = 'message error show';
                    return;
                }}
                
                button.disabled = true;
                button.textContent = 'Sending...';
                
                try {{
                    const response = await fetch('/send-email', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ email: email }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.success) {{
                        messageEl.textContent = '✓ Brief sent! Check your email.';
                        messageEl.className = 'message success show';
                        document.getElementById('emailInput').value = '';
                    }} else {{
                        messageEl.textContent = '✗ Error: ' + data.error;
                        messageEl.className = 'message error show';
                    }}
                }} catch (error) {{
                    messageEl.textContent = '✗ Error: ' + error.message;
                    messageEl.className = 'message error show';
                }} finally {{
                    button.disabled = false;
                    button.textContent = 'Send to My Email';
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    return html


@app.route("/")
def index():
    """Main form page where users select topics."""
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>☀️ Morning Information Diet</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                max-width: 500px;
                width: 100%;
                padding: 40px;
            }
            h1 {
                font-size: 32px;
                color: #333;
                margin-bottom: 8px;
            }
            .subtitle {
                color: #666;
                font-size: 14px;
                margin-bottom: 30px;
            }
            .section {
                margin-bottom: 30px;
            }
            .section-title {
                font-weight: 600;
                color: #333;
                margin-bottom: 12px;
                font-size: 14px;
            }
            .checkbox-group {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .checkbox-item {
                display: flex;
                align-items: center;
                gap: 10px;
                cursor: pointer;
                padding: 8px;
                border-radius: 4px;
                transition: background 0.2s;
            }
            .checkbox-item:hover {
                background: #f9f9f9;
            }
            .checkbox-item input {
                cursor: pointer;
                width: 18px;
                height: 18px;
            }
            .checkbox-item label {
                cursor: pointer;
                font-size: 14px;
                color: #333;
                flex: 1;
            }
            textarea {
                width: 100%;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
                font-family: inherit;
                resize: vertical;
                min-height: 80px;
            }
            .generate-button {
                width: 100%;
                padding: 14px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s;
            }
            .generate-button:hover {
                transform: translateY(-2px);
            }
            .generate-button:disabled {
                opacity: 0.7;
                cursor: not-allowed;
            }
            .loading {
                display: none;
                text-align: center;
                padding: 20px;
                color: #667eea;
            }
            .spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .error {
                display: none;
                background: #f8d7da;
                color: #721c24;
                padding: 12px;
                border-radius: 4px;
                margin-bottom: 20px;
                border: 1px solid #f5c6cb;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>☀️ Morning Brief</h1>
            <p class="subtitle">Select topics you care about, get one curated update</p>
            
            <div id="error" class="error"></div>
            
            <form id="briefForm">
                <div class="section">
                    <div class="section-title">📰 Popular Topics</div>
                    <div class="checkbox-group">
                        <div class="checkbox-item">
                            <input type="checkbox" id="topic_ai" name="topics" value="artificial intelligence" checked>
                            <label for="topic_ai">Artificial Intelligence</label>
                        </div>
                        <div class="checkbox-item">
                            <input type="checkbox" id="topic_climate" name="topics" value="climate technology" checked>
                            <label for="topic_climate">Climate Technology</label>
                        </div>
                        <div class="checkbox-item">
                            <input type="checkbox" id="topic_energy" name="topics" value="renewable energy">
                            <label for="topic_energy">Renewable Energy</label>
                        </div>
                        <div class="checkbox-item">
                            <input type="checkbox" id="topic_quantum" name="topics" value="quantum computing">
                            <label for="topic_quantum">Quantum Computing</label>
                        </div>
                        <div class="checkbox-item">
                            <input type="checkbox" id="topic_space" name="topics" value="space exploration">
                            <label for="topic_space">Space Exploration</label>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">✏️ Add Your Own Topics</div>
                    <textarea 
                        id="customTopics" 
                        placeholder="Enter topics separated by commas&#10;Example: biotech, startups, education"
                    ></textarea>
                </div>
                
                <button type="submit" class="generate-button" id="generateBtn">
                    Generate My Brief
                </button>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p>Generating your brief...</p>
                </div>
            </form>
        </div>
        
        <script>
            document.getElementById('briefForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                // Get checked topics
                const checked = Array.from(document.querySelectorAll('input[name="topics"]:checked'))
                    .map(el => el.value);
                
                // Get custom topics
                const custom = document.getElementById('customTopics').value
                    .split(',')
                    .map(t => t.trim())
                    .filter(t => t);
                
                const allTopics = [...checked, ...custom];
                
                if (allTopics.length === 0) {
                    document.getElementById('error').textContent = 'Please select at least one topic';
                    document.getElementById('error').style.display = 'block';
                    return;
                }
                
                document.getElementById('error').style.display = 'none';
                document.getElementById('generateBtn').disabled = true;
                document.getElementById('loading').style.display = 'block';
                
                try {
                    const response = await fetch('/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ topics: allTopics })
                    });
                    
                    if (!response.ok) {
                        throw new Error('Generation failed');
                    }
                    
                    // Get the HTML and display it
                    const html = await response.text();
                    document.open();
                    document.write(html);
                    document.close();
                } catch (error) {
                    document.getElementById('error').textContent = 'Error: ' + error.message;
                    document.getElementById('error').style.display = 'block';
                } finally {
                    document.getElementById('generateBtn').disabled = false;
                    document.getElementById('loading').style.display = 'none';
                }
            });
        </script>
    </body>
    </html>
    """


@app.route("/generate", methods=["POST"])
def generate():
    """Generate briefs for selected topics."""
    
    data = request.json
    topics = data.get("topics", [])
    
    if not topics:
        return jsonify({"error": "No topics provided"}), 400
    
    try:
        # Fetch articles for all topics
        articles_by_topic = fetch_articles(topics)
        
        # Store in memory for email sending
        global current_briefs
        current_briefs = articles_by_topic
        
        # Generate HTML with briefs
        html = generate_html_brief(articles_by_topic)
        
        return html, 200, {"Content-Type": "text/html"}
    
    except Exception as e:
        print(f"\n❌ ERROR in /generate:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/send-email", methods=["POST"])
def send_email():
    """Send the brief to an email address (or simulate sending for now)."""
    
    data = request.json
    recipient_email = data.get("email")
    
    if not recipient_email:
        return jsonify({"success": False, "error": "No email provided"}), 400
    
    # Get SMTP credentials from env
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    
    # If no email config, just simulate success (for testing)
    if not sender_email or not sender_password:
        print(f"📧 [SIMULATED] Brief would be sent to {recipient_email}")
        return jsonify({
            "success": True, 
            "message": f"✓ Brief sent to {recipient_email}! (Note: Email feature is disabled for testing. In production, set SENDER_EMAIL and SENDER_PASSWORD env vars.)"
        })
    
    # If we have credentials, actually send the email
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        
        # Generate the email HTML from current briefs
        email_html = generate_html_brief(current_briefs)
        
        # Create email
        message = MIMEMultipart("alternative")
        message["Subject"] = "☀️ Your Morning Brief"
        message["From"] = sender_email
        message["To"] = recipient_email
        
        message.attach(MIMEText(email_html, "html"))
        
        # Send via SMTP
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
        
        print(f"✓ Email sent to {recipient_email}")
        return jsonify({"success": True, "message": f"✓ Brief sent to {recipient_email}!"})
    
    except Exception as e:
        print(f"✗ Email error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("🚀 Starting Morning Brief Web App (REDESIGNED)")
    print("   Open: http://localhost:5000")
    print("\n   To send emails, set:")
    print("   export SENDER_EMAIL='your@gmail.com'")
    print("   export SENDER_PASSWORD='your-app-password'")
    app.run(debug=True)