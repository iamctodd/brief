#!/usr/bin/env python3
from flask import Flask, request, jsonify
import os
import markdown2
import requests
from anthropic import Anthropic
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
client = None

def get_client():
    global client
    if client is None:
        # Clear proxy env vars (both uppercase and lowercase)
        saved = {}
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']:
            if key in os.environ:
                saved[key] = os.environ.pop(key)
        try:
            client = Anthropic()
        finally:
            # Restore proxy env vars
            for key, val in saved.items():
                os.environ[key] = val
    return client

current_briefs = {}

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
            "content": f"""Synthesize this news about {topic} into a SHORT (2-3 sentences), POSITIVE morning brief.

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
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morning Brief</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: #fff; color: #222; }
        .container { max-width: 600px; margin: 0 auto; padding: 80px 24px; }
        .header { text-align: center; margin-bottom: 60px; }
        .header h1 { font-size: 42px; font-weight: 700; margin-bottom: 12px; }
        .header p { font-size: 16px; color: #666; }
        .form-section { margin-bottom: 40px; }
        .section-title { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #666; margin-bottom: 16px; }
        .checkbox-group { display: flex; flex-direction: column; gap: 12px; }
        .checkbox-item { display: flex; align-items: center; gap: 12px; padding: 12px; border-radius: 4px; cursor: pointer; }
        .checkbox-item:hover { background: #f5f5f5; }
        .checkbox-item input { cursor: pointer; accent-color: #000; }
        .checkbox-item label { cursor: pointer; flex: 1; }
        textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; font-family: inherit; min-height: 80px; }
        textarea:focus { outline: none; border-color: #000; }
        .btn { width: 100%; padding: 14px; background: #000; color: white; border: none; border-radius: 4px; font-size: 15px; font-weight: 600; cursor: pointer; }
        .btn:hover { background: #333; }
        .btn:disabled { background: #ccc; }
        .error { display: none; background: #fce8e6; color: #c5221f; padding: 12px; border-radius: 4px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Morning Brief</h1>
            <p>Select topics. Get curated news.</p>
        </div>
        <div id="error" class="error"></div>
        <form id="form">
            <div class="form-section">
                <div class="section-title">Popular Topics</div>
                <div class="checkbox-group">
                    <div class="checkbox-item">
                        <input type="checkbox" id="ai" name="topics" value="artificial intelligence" checked>
                        <label for="ai">Artificial Intelligence</label>
                    </div>
                    <div class="checkbox-item">
                        <input type="checkbox" id="climate" name="topics" value="climate technology" checked>
                        <label for="climate">Climate Technology</label>
                    </div>
                    <div class="checkbox-item">
                        <input type="checkbox" id="energy" name="topics" value="renewable energy">
                        <label for="energy">Renewable Energy</label>
                    </div>
                </div>
            </div>
            <div class="form-section">
                <div class="section-title">Custom Topics</div>
                <textarea id="custom" placeholder="Comma-separated&#10;Example: startups, space, biotech"></textarea>
            </div>
            <button type="submit" class="btn" id="btn">Generate My Brief</button>
        </form>
    </div>
    <script>
        document.getElementById('form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const topics = Array.from(document.querySelectorAll('input[name="topics"]:checked')).map(el => el.value);
            const custom = document.getElementById('custom').value.split(',').map(t => t.trim()).filter(t => t);
            const allTopics = [...topics, ...custom];
            if (!allTopics.length) { alert('Select at least one topic'); return; }
            document.getElementById('btn').disabled = true;
            document.getElementById('btn').textContent = 'Generating...';
            try {
                const res = await fetch('/generate', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({topics: allTopics}) });
                if (!res.ok) throw new Error('Failed');
                const html = await res.text();
                document.open(); document.write(html); document.close();
            } catch (e) {
                document.getElementById('error').textContent = 'Error: ' + e.message;
                document.getElementById('error').style.display = 'block';
                document.getElementById('btn').disabled = false;
                document.getElementById('btn').textContent = 'Generate My Brief';
            }
        });
    </script>
</body>
</html>"""

@app.route("/generate", methods=["POST"])
def generate():
    topics = request.json.get("topics", [])
    if not topics:
        return jsonify({"error": "No topics"}), 400
    
    articles_by_topic = fetch_articles(topics)
    global current_briefs
    current_briefs = articles_by_topic
    
    briefs_html = ""
    for topic in topics:
        articles = articles_by_topic.get(topic, [])
        if articles:
            brief_text = synthesize_brief(topic, articles)
            brief_html = markdown2.markdown(brief_text, extras=['nl2br'])
            
            articles_html = "\n".join([
                f"""<article style="border: 1px solid #e0e0e0; border-radius: 4px; padding: 24px; margin-bottom: 20px;">
                    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #666; margin-bottom: 12px;">{a['source']}</div>
                    <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 12px;"><a href="{a['url']}" target="_blank" style="color: #000; text-decoration: none;">{a['title']}</a></h3>
                    <p style="font-size: 14px; color: #666; margin-bottom: 16px;">{a['description']}</p>
                    <time style="font-size: 12px; color: #999;">{a['published']}</time>
                </article>"""
                for a in articles[:3]
            ])
            
            briefs_html += f"""
            <div style="margin-bottom: 80px;">
                <h2 style="font-size: 32px; font-weight: 700; margin-bottom: 32px;">{topic.title()}</h2>
                <div style="background: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 4px; padding: 32px; margin-bottom: 40px;">
                    {brief_html}
                </div>
                <h3 style="font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #666; margin-bottom: 24px;">Today's Top Stories</h3>
                {articles_html}
            </div>
            """
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Morning Brief</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: #fff; color: #222; line-height: 1.6; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 60px 24px; }}
        .header {{ text-align: center; margin-bottom: 60px; padding-bottom: 40px; border-bottom: 1px solid #e0e0e0; }}
        .header h1 {{ font-size: 48px; font-weight: 700; margin-bottom: 12px; }}
        .header p {{ font-size: 16px; color: #666; }}
        .email-section {{ background: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 4px; padding: 40px; margin-top: 60px; text-align: center; }}
        .email-section h3 {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; }}
        .email-section p {{ font-size: 14px; color: #666; margin-bottom: 24px; }}
        input[type="email"] {{ width: 100%; max-width: 400px; padding: 12px 16px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; margin-bottom: 16px; }}
        input[type="email"]:focus {{ outline: none; border-color: #000; }}
        button {{ background: #000; color: white; padding: 12px 32px; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; font-size: 14px; }}
        button:hover {{ background: #333; }}
        .message {{ padding: 12px 16px; border-radius: 4px; margin-bottom: 16px; display: none; font-size: 14px; }}
        .message.success {{ background: #e6f4ea; color: #137333; border: 1px solid #81c995; }}
        .message.error {{ background: #fce8e6; color: #c5221f; border: 1px solid #f1ddd9; }}
        .message.show {{ display: block; }}
        .footer {{ text-align: center; margin-top: 60px; padding-top: 40px; border-top: 1px solid #e0e0e0; font-size: 12px; color: #999; }}
        .footer a {{ color: #0066cc; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Your Morning Brief</h1>
            <p>Curated news to start your day informed</p>
        </div>
        {briefs_html}
        <div class="email-section">
            <h3>Get This in Your Inbox</h3>
            <p>Receive briefs like this every morning</p>
            <div id="message" class="message"></div>
            <input type="email" id="email" placeholder="your@email.com" required>
            <button onclick="sendEmail()">Send to My Email</button>
        </div>
        <div class="footer">
            <p><a href="/">← Edit Topics</a></p>
        </div>
    </div>
    <script>
        async function sendEmail() {{
            const email = document.getElementById('email').value;
            const msg = document.getElementById('message');
            if (!email) {{ msg.textContent = 'Enter email'; msg.className = 'message error show'; return; }}
            try {{
                const res = await fetch('/send-email', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{email}}) }});
                const data = await res.json();
                if (data.success) {{ msg.textContent = '✓ Sent!'; msg.className = 'message success show'; document.getElementById('email').value = ''; }}
                else {{ msg.textContent = '✗ Error: ' + data.error; msg.className = 'message error show'; }}
            }} catch (e) {{ msg.textContent = '✗ Error'; msg.className = 'message error show'; }}
        }}
    </script>
</body>
</html>"""
    
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
        # Generate full brief HTML from current_briefs
        briefs_html = ""
        for topic, articles in current_briefs.items():
            if articles:
                brief_text = synthesize_brief(topic, articles)
                brief_html = markdown2.markdown(brief_text, extras=['nl2br'])
                
                articles_html = "\n".join([
                    f"""<article style="border: 1px solid #e0e0e0; border-radius: 4px; padding: 24px; margin-bottom: 20px;">
                    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #666; margin-bottom: 12px;">{a['source']}</div>
                    <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 12px;"><a href="{a['url']}" target="_blank" style="color: #000; text-decoration: none;">{a['title']}</a></h3>
                    <p style="font-size: 14px; color: #666; margin-bottom: 16px;">{a['description']}</p>
                    <time style="font-size: 12px; color: #999;">{a['published']}</time>
                </article>"""
                    for a in articles[:3]
                ])
                
                briefs_html += f"""
                <div style="margin-bottom: 80px;">
                    <h2 style="font-size: 32px; font-weight: 700; margin-bottom: 32px;">{topic.title()}</h2>
                    <div style="background: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 4px; padding: 32px; margin-bottom: 40px;">
                        {brief_html}
                    </div>
                    <h3 style="font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #666; margin-bottom: 24px;">Today's Top Stories</h3>
                    {articles_html}
                </div>
                """
        
        email_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: #fff; color: #222; line-height: 1.6; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 60px 24px; }}
        .header {{ text-align: center; margin-bottom: 60px; padding-bottom: 40px; border-bottom: 1px solid #e0e0e0; }}
        .header h1 {{ font-size: 48px; font-weight: 700; margin-bottom: 12px; }}
        .header p {{ font-size: 16px; color: #666; }}
        .footer {{ text-align: center; margin-top: 60px; padding-top: 40px; border-top: 1px solid #e0e0e0; font-size: 12px; color: #999; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Your Morning Brief</h1>
            <p>Curated news to start your day informed</p>
        </div>
        {briefs_html}
        <div class="footer">
            <p>Your information diet delivered daily</p>
        </div>
    </div>
</body>
</html>"""
        
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
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    print("🚀 Morning Brief - running on http://localhost:5000")
    app.run(debug=True)