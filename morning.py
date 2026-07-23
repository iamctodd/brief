#!/usr/bin/env python3
"""
Morning Brief Web App - Professional Redesign
Modern, clean design inspired by Bloomberg, CBS News, and The Next Web.
Full email delivery support.

Run: python morning.py
Then open: http://localhost:5000
"""

from flask import Flask, request, jsonify
import os
import markdown2
import requests
import json
from anthropic import Anthropic
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

# Initialize Claude client (lazy)
client = None

def get_client():
    global client
    if client is None:
        # Temporarily clear proxy env vars that Fly.io sets
        old_http = os.environ.pop('HTTP_PROXY', None)
        old_https = os.environ.pop('HTTPS_PROXY', None)
        old_all = os.environ.pop('ALL_PROXY', None)
        
        try:
            client = Anthropic()
        finally:
            # Restore env vars
            if old_http:
                os.environ['HTTP_PROXY'] = old_http
            if old_https:
                os.environ['HTTPS_PROXY'] = old_https
            if old_all:
                os.environ['ALL_PROXY'] = old_all
    return client


# Store briefs for email sending
current_briefs = {}


def fetch_articles(topics: list, max_per_topic: int = 5) -> dict:
    """Fetch articles for multiple topics."""
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
                        "source": a["source"],
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
    
    prompt = f"""You are a professional morning news curator. Synthesize this news about {topic} 
into a SHORT (2-3 sentences), POSITIVE, ACTIONABLE morning brief.

Rules:
- Focus on opportunities, trends, and progress
- Be insightful and forward-looking
- End with "Today's focus:" followed by one actionable insight
- Keep it under 150 words
- Use professional language

Articles:
{articles_text}

Write the brief:"""
    
    message = get_client().messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text


def generate_html_brief(topics_and_articles: dict) -> str:
    """Generate professional HTML page with all briefs."""
    
    briefs_html = ""
    
    for topic, articles in topics_and_articles.items():
        if articles:
            brief_text = synthesize_brief(topic, articles)
            brief_html = markdown2.markdown(brief_text, extras=['nl2br'])
            
            articles_html = "\n".join([
                f"""
                <article class="news-card">
                    <div class="news-source">{a['source']}</div>
                    <h3 class="news-title"><a href="{a['url']}" target="_blank" rel="noopener">{a['title']}</a></h3>
                    <p class="news-description">{a['description']}</p>
                    <time class="news-date">{a['published']}</time>
                </article>
                """
                for a in articles[:3]
            ])
            
            briefs_html += f"""
            <section class="brief-section">
                <div class="section-divider"></div>
                <h2 class="section-title">{topic.title()}</h2>
                
                <div class="brief-card">
                    <div class="brief-content">
                        {brief_html}
                    </div>
                </div>
                
                <h3 class="subsection-title">Today's Top Stories</h3>
                <div class="news-grid">
                    {articles_html}
                </div>
            </section>
            """
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Your Morning Brief</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: #ffffff;
                color: #222;
                line-height: 1.6;
            }}
            
            .container {{
                max-width: 900px;
                margin: 0 auto;
                padding: 60px 24px;
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 60px;
                padding-bottom: 40px;
                border-bottom: 1px solid #e0e0e0;
            }}
            
            .header h1 {{
                font-size: 48px;
                font-weight: 700;
                margin-bottom: 12px;
                letter-spacing: -1px;
                color: #000;
            }}
            
            .header p {{
                font-size: 16px;
                color: #666;
                font-weight: 400;
            }}
            
            .brief-section {{
                margin-bottom: 80px;
            }}
            
            .section-divider {{
                height: 1px;
                background: #e0e0e0;
                margin-bottom: 40px;
            }}
            
            .section-title {{
                font-size: 32px;
                font-weight: 700;
                margin-bottom: 32px;
                color: #000;
                letter-spacing: -0.5px;
            }}
            
            .brief-card {{
                background: #f8f8f8;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 32px;
                margin-bottom: 40px;
                line-height: 1.8;
                font-size: 16px;
            }}
            
            .brief-content {{
                color: #333;
            }}
            
            .brief-content strong {{
                color: #000;
                font-weight: 600;
            }}
            
            .brief-content em {{
                color: #666;
                font-style: italic;
            }}
            
            .subsection-title {{
                font-size: 14px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #666;
                margin-bottom: 24px;
            }}
            
            .news-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 24px;
                margin-bottom: 60px;
            }}
            
            .news-card {{
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 24px;
                transition: all 0.3s ease;
                display: flex;
                flex-direction: column;
                height: 100%;
                background: #fff;
            }}
            
            .news-card:hover {{
                border-color: #000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }}
            
            .news-source {{
                display: inline-block;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: #666;
                margin-bottom: 12px;
                background: #f0f0f0;
                padding: 4px 8px;
                border-radius: 2px;
                width: fit-content;
            }}
            
            .news-title {{
                font-size: 18px;
                font-weight: 600;
                line-height: 1.3;
                margin-bottom: 12px;
                color: #000;
            }}
            
            .news-title a {{
                color: #000;
                text-decoration: none;
                transition: color 0.2s;
            }}
            
            .news-title a:hover {{
                color: #0066cc;
            }}
            
            .news-description {{
                font-size: 14px;
                color: #666;
                line-height: 1.6;
                margin-bottom: 16px;
                flex-grow: 1;
            }}
            
            .news-date {{
                font-size: 12px;
                color: #999;
                display: block;
            }}
            
            .email-section {{
                background: #f8f8f8;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 40px;
                margin-top: 60px;
                text-align: center;
            }}
            
            .email-section h3 {{
                font-size: 24px;
                font-weight: 700;
                margin-bottom: 12px;
                color: #000;
            }}
            
            .email-section p {{
                font-size: 14px;
                color: #666;
                margin-bottom: 24px;
            }}
            
            .email-input {{
                width: 100%;
                max-width: 400px;
                padding: 12px 16px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
                margin-bottom: 16px;
                transition: border-color 0.2s;
            }}
            
            .email-input:focus {{
                outline: none;
                border-color: #000;
            }}
            
            .email-button {{
                background: #000;
                color: white;
                padding: 12px 32px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 600;
                font-size: 14px;
                transition: background 0.2s;
            }}
            
            .email-button:hover {{
                background: #333;
            }}
            
            .email-button:disabled {{
                background: #ccc;
                cursor: not-allowed;
            }}
            
            .message {{
                padding: 12px 16px;
                border-radius: 4px;
                margin-bottom: 16px;
                display: none;
                font-size: 14px;
                font-weight: 500;
            }}
            
            .message.success {{
                background: #e6f4ea;
                color: #137333;
                border: 1px solid #81c995;
            }}
            
            .message.error {{
                background: #fce8e6;
                color: #c5221f;
                border: 1px solid #f1ddd9;
            }}
            
            .message.show {{
                display: block;
            }}
            
            .footer {{
                text-align: center;
                margin-top: 60px;
                padding-top: 40px;
                border-top: 1px solid #e0e0e0;
                font-size: 12px;
                color: #999;
            }}
            
            .footer a {{
                color: #0066cc;
                text-decoration: none;
            }}
            
            .footer a:hover {{
                text-decoration: underline;
            }}
            
            @media (max-width: 768px) {{
                .container {{ padding: 40px 16px; }}
                .header h1 {{ font-size: 36px; }}
                .section-title {{ font-size: 24px; }}
                .news-grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header class="header">
                <h1>Your Morning Brief</h1>
                <p>Curated news to start your day informed</p>
            </header>
            
            {briefs_html}
            
            <div class="email-section">
                <h3>Get This in Your Inbox</h3>
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
            
            <footer class="footer">
                <p><a href="/">← Edit Topics</a></p>
            </footer>
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
                        messageEl.textContent = '✓ Brief sent! Check your inbox.';
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
    """Main form page - modern, clean design."""
    
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Morning Brief - Select Topics</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: #ffffff;
                color: #222;
            }
            
            .container {
                max-width: 600px;
                margin: 0 auto;
                padding: 80px 24px;
            }
            
            .header {
                margin-bottom: 60px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 42px;
                font-weight: 700;
                margin-bottom: 12px;
                letter-spacing: -1px;
            }
            
            .header p {
                font-size: 16px;
                color: #666;
                font-weight: 400;
            }
            
            .form-section {
                margin-bottom: 40px;
            }
            
            .section-title {
                font-size: 13px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #666;
                margin-bottom: 16px;
            }
            
            .checkbox-group {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            
            .checkbox-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px;
                border-radius: 4px;
                cursor: pointer;
                transition: background 0.2s;
            }
            
            .checkbox-item:hover {
                background: #f5f5f5;
            }
            
            .checkbox-item input[type="checkbox"] {
                cursor: pointer;
                width: 18px;
                height: 18px;
                accent-color: #000;
            }
            
            .checkbox-item label {
                cursor: pointer;
                font-size: 15px;
                color: #222;
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
                transition: border-color 0.2s;
            }
            
            textarea:focus {
                outline: none;
                border-color: #000;
            }
            
            .generate-button {
                width: 100%;
                padding: 14px;
                background: #000;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.2s;
            }
            
            .generate-button:hover {
                background: #333;
            }
            
            .generate-button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            
            .loading {
                display: none;
                text-align: center;
                padding: 20px;
                color: #666;
            }
            
            .spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 2px solid #f0f0f0;
                border-top-color: #000;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            .error {
                display: none;
                background: #fce8e6;
                color: #c5221f;
                padding: 12px;
                border-radius: 4px;
                margin-bottom: 20px;
                border: 1px solid #f1ddd9;
                font-size: 14px;
            }
            
            @media (max-width: 768px) {
                .container { padding: 40px 16px; }
                .header h1 { font-size: 32px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Morning Brief</h1>
                <p>Select topics. Get curated news.</p>
            </div>
            
            <div id="error" class="error"></div>
            
            <form id="briefForm">
                <div class="form-section">
                    <div class="section-title">Popular Topics</div>
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
                            <input type="checkbox" id="topic_tech" name="topics" value="technology news">
                            <label for="topic_tech">Technology News</label>
                        </div>
                        <div class="checkbox-item">
                            <input type="checkbox" id="topic_business" name="topics" value="business">
                            <label for="topic_business">Business</label>
                        </div>
                    </div>
                </div>
                
                <div class="form-section">
                    <div class="section-title">Add Custom Topics</div>
                    <textarea 
                        id="customTopics" 
                        placeholder="Enter topics separated by commas&#10;Example: startups, biotech, space"
                    ></textarea>
                </div>
                
                <button type="submit" class="generate-button" id="generateBtn">
                    Generate My Brief
                </button>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p style="margin-top: 12px;">Generating your brief...</p>
                </div>
            </form>
        </div>
        
        <script>
            document.getElementById('briefForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const checked = Array.from(document.querySelectorAll('input[name="topics"]:checked'))
                    .map(el => el.value);
                
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
                    
                    if (!response.ok) throw new Error('Generation failed');
                    
                    const html = await response.text();
                    document.open();
                    document.write(html);
                    document.close();
                } catch (error) {
                    document.getElementById('error').textContent = '✗ Error: ' + error.message;
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
    """Generate briefs for selected topics - with immediate page load."""
    
    data = request.json
    topics = data.get("topics", [])
    
    if not topics:
        return jsonify({"error": "No topics provided"}), 400
    
    try:
        articles_by_topic = fetch_articles(topics)
        
        # Store in memory for email sending
        global current_briefs
        current_briefs = articles_by_topic
        
        # Return HTML page skeleton with articles immediately
        # Briefs will load via AJAX
        return generate_html_skeleton(articles_by_topic, topics), 200, {"Content-Type": "text/html"}
    
    except Exception as e:
        print(f"\n❌ ERROR in /generate:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/generate-brief", methods=["POST"])
def generate_brief():
    """Generate a single brief (called via AJAX)."""
    
    data = request.json
    topic = data.get("topic")
    articles = data.get("articles")
    
    if not topic or not articles:
        return jsonify({"error": "Missing topic or articles"}), 400
    
    try:
        brief_text = synthesize_brief(topic, articles)
        brief_html = markdown2.markdown(brief_text, extras=['nl2br'])
        
        return jsonify({
            "success": True,
            "topic": topic,
            "brief": brief_html
        })
    
    except Exception as e:
        print(f"Error generating brief for {topic}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def generate_html_skeleton(topics_and_articles: dict, topics: list) -> str:
    """Generate HTML page skeleton with articles but empty briefs."""
    
    briefs_skeleton = ""
    
    for topic in topics:
        articles = topics_and_articles.get(topic, [])
        
        if articles:
            articles_html = "\n".join([
                f"""
                <article class="news-card">
                    <div class="news-source">{a['source']}</div>
                    <h3 class="news-title"><a href="{a['url']}" target="_blank" rel="noopener">{a['title']}</a></h3>
                    <p class="news-description">{a['description']}</p>
                    <time class="news-date">{a['published']}</time>
                </article>
                """
                for a in articles[:3]
            ])
            
            # Escape articles as JSON for passing to JavaScript
            articles_json = json.dumps([
                {
                    "title": a["title"],
                    "description": a["description"],
                    "url": a["url"],
                    "source": a["source"],
                    "published": a["published"]
                }
                for a in articles
            ])
            
            briefs_skeleton += f"""
            <section class="brief-section">
                <div class="section-divider"></div>
                <h2 class="section-title">{topic.title()}</h2>
                
                <div class="brief-card" id="brief-{topic}">
                    <div class="brief-content">
                        <div class="brief-loading">
                            <div class="spinner-small"></div>
                            <p>Generating your brief...</p>
                        </div>
                    </div>
                </div>
                
                <h3 class="subsection-title">Today's Top Stories</h3>
                <div class="news-grid">
                    {articles_html}
                </div>
                
                <script>
                    // Generate brief for this topic
                    fetch('/generate-brief', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            topic: "{topic}",
                            articles: {articles_json}
                        }})
                    }})
                    .then(r => r.json())
                    .then(data => {{
                        if (data.success) {{
                            document.getElementById('brief-{topic}').innerHTML = '<div class="brief-content">' + data.brief + '</div>';
                        }} else {{
                            document.getElementById('brief-{topic}').innerHTML = '<p style="color: red;">Error generating brief</p>';
                        }}
                    }})
                    .catch(err => {{
                        document.getElementById('brief-{topic}').innerHTML = '<p style="color: red;">Error: ' + err.message + '</p>';
                    }});
                </script>
            </section>
            """
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Your Morning Brief</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: #ffffff;
                color: #222;
                line-height: 1.6;
            }}
            
            .container {{
                max-width: 900px;
                margin: 0 auto;
                padding: 60px 24px;
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 60px;
                padding-bottom: 40px;
                border-bottom: 1px solid #e0e0e0;
            }}
            
            .header h1 {{
                font-size: 48px;
                font-weight: 700;
                margin-bottom: 12px;
                letter-spacing: -1px;
                color: #000;
            }}
            
            .header p {{
                font-size: 16px;
                color: #666;
                font-weight: 400;
            }}
            
            .brief-section {{
                margin-bottom: 80px;
            }}
            
            .section-divider {{
                height: 1px;
                background: #e0e0e0;
                margin-bottom: 40px;
            }}
            
            .section-title {{
                font-size: 32px;
                font-weight: 700;
                margin-bottom: 32px;
                color: #000;
                letter-spacing: -0.5px;
            }}
            
            .brief-card {{
                background: #f8f8f8;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 32px;
                margin-bottom: 40px;
                line-height: 1.8;
                font-size: 16px;
                min-height: 100px;
                transition: all 0.3s ease;
            }}
            
            .brief-loading {{
                display: flex;
                align-items: center;
                gap: 12px;
                color: #666;
            }}
            
            .spinner-small {{
                width: 16px;
                height: 16px;
                border: 2px solid #f0f0f0;
                border-top-color: #000;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }}
            
            @keyframes spin {{
                to {{ transform: rotate(360deg); }}
            }}
            
            .brief-content {{
                color: #333;
            }}
            
            .brief-content strong {{
                color: #000;
                font-weight: 600;
            }}
            
            .brief-content em {{
                color: #666;
                font-style: italic;
            }}
            
            .subsection-title {{
                font-size: 14px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #666;
                margin-bottom: 24px;
            }}
            
            .news-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 24px;
                margin-bottom: 60px;
            }}
            
            .news-card {{
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 24px;
                transition: all 0.3s ease;
                display: flex;
                flex-direction: column;
                height: 100%;
                background: #fff;
            }}
            
            .news-card:hover {{
                border-color: #000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }}
            
            .news-source {{
                display: inline-block;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: #666;
                margin-bottom: 12px;
                background: #f0f0f0;
                padding: 4px 8px;
                border-radius: 2px;
                width: fit-content;
            }}
            
            .news-title {{
                font-size: 18px;
                font-weight: 600;
                line-height: 1.3;
                margin-bottom: 12px;
                color: #000;
            }}
            
            .news-title a {{
                color: #000;
                text-decoration: none;
                transition: color 0.2s;
            }}
            
            .news-title a:hover {{
                color: #0066cc;
            }}
            
            .news-description {{
                font-size: 14px;
                color: #666;
                line-height: 1.6;
                margin-bottom: 16px;
                flex-grow: 1;
            }}
            
            .news-date {{
                font-size: 12px;
                color: #999;
                display: block;
            }}
            
            .email-section {{
                background: #f8f8f8;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 40px;
                margin-top: 60px;
                text-align: center;
            }}
            
            .email-section h3 {{
                font-size: 24px;
                font-weight: 700;
                margin-bottom: 12px;
                color: #000;
            }}
            
            .email-section p {{
                font-size: 14px;
                color: #666;
                margin-bottom: 24px;
            }}
            
            .email-input {{
                width: 100%;
                max-width: 400px;
                padding: 12px 16px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
                margin-bottom: 16px;
                transition: border-color 0.2s;
            }}
            
            .email-input:focus {{
                outline: none;
                border-color: #000;
            }}
            
            .email-button {{
                background: #000;
                color: white;
                padding: 12px 32px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 600;
                font-size: 14px;
                transition: background 0.2s;
            }}
            
            .email-button:hover {{
                background: #333;
            }}
            
            .email-button:disabled {{
                background: #ccc;
                cursor: not-allowed;
            }}
            
            .message {{
                padding: 12px 16px;
                border-radius: 4px;
                margin-bottom: 16px;
                display: none;
                font-size: 14px;
                font-weight: 500;
            }}
            
            .message.success {{
                background: #e6f4ea;
                color: #137333;
                border: 1px solid #81c995;
            }}
            
            .message.error {{
                background: #fce8e6;
                color: #c5221f;
                border: 1px solid #f1ddd9;
            }}
            
            .message.show {{
                display: block;
            }}
            
            .footer {{
                text-align: center;
                margin-top: 60px;
                padding-top: 40px;
                border-top: 1px solid #e0e0e0;
                font-size: 12px;
                color: #999;
            }}
            
            .footer a {{
                color: #0066cc;
                text-decoration: none;
            }}
            
            .footer a:hover {{
                text-decoration: underline;
            }}
            
            @media (max-width: 768px) {{
                .container {{ padding: 40px 16px; }}
                .header h1 {{ font-size: 36px; }}
                .section-title {{ font-size: 24px; }}
                .news-grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header class="header">
                <h1>Your Morning Brief</h1>
                <p>Curated news to start your day informed</p>
            </header>
            
            {briefs_skeleton}
            
            <div class="email-section">
                <h3>Get This in Your Inbox</h3>
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
            
            <footer class="footer">
                <p><a href="/">← Edit Topics</a></p>
            </footer>
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
                        messageEl.textContent = '✓ Brief sent! Check your inbox.';
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


@app.route("/send-email", methods=["POST"])
def send_email():
    """Send the brief to an email address."""
    
    data = request.json
    recipient_email = data.get("email")
    
    if not recipient_email:
        return jsonify({"success": False, "error": "No email provided"}), 400
    
    # Get SMTP credentials from env
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    
    # If no email config, simulate success for testing
    if not sender_email or not sender_password:
        print(f"📧 [SIMULATED] Brief would be sent to {recipient_email}")
        return jsonify({
            "success": True, 
            "message": f"✓ Email feature demo. To enable real delivery, set SENDER_EMAIL and SENDER_PASSWORD."
        })
    
    # Send real email
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        
        # Generate the email HTML from current briefs
        email_html = generate_html_brief(current_briefs)
        
        # Create email
        message = MIMEMultipart("alternative")
        message["Subject"] = "Your Morning Brief"
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
    print("🚀 Starting Morning Brief Web App")
    print("   Open: http://localhost:5000")
    app.run(debug=True)