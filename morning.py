#!/usr/bin/env python3
"""
Morning Information Diet Agent - Version 2
Adds scheduling, positivity filtering, and email delivery.

New concepts: 
- APScheduler for background tasks
- Sentiment analysis for filtering
- Email delivery via SMTP
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
import httpx

client = Anthropic()

class MorningNewsAgent:
    """Stateful agent that manages configuration and scheduling."""
    
    def __init__(self, config: dict):
        """
        Initialize the agent with configuration.
        
        Args:
            config: Dictionary with keys:
                - topic: The domain to track
                - schedule_time: "HH:MM" format (e.g., "07:30")
                - email_to: Recipient email
                - positivity_threshold: 0-1 score (higher = more positive articles only)
        """
        self.config = config
        self.scheduler = BackgroundScheduler()
        
    def assess_article_sentiment(self, article: dict) -> float:
        """
        Use Claude to quickly assess if an article is positive/constructive.
        
        Returns a score 0-1 where:
        - 0.0 = pure doom/crisis
        - 0.5 = neutral/mixed
        - 1.0 = optimistic/opportunity-focused
        
        Args:
            article: Article dictionary with title and description
        
        Returns:
            Sentiment score 0-1
        """
        
        prompt = f"""Rate this article about {self.config['topic']} on a scale of 0-1 for constructiveness and forward-looking perspective.

0.0 = Pure crisis/doom, no constructive angle
0.3 = Negative but with some context
0.5 = Neutral/balanced reporting
0.7 = Positive with constructive solutions mentioned
1.0 = Clearly optimistic, opportunity-focused, progress-driven

Article:
Title: {article['title']}
Description: {article['description']}

Respond with ONLY a single number 0-1.0 with one decimal place. Example: 0.7"""
        
        try:
            message = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}]
            )
            score_text = message.content[0].text.strip()
            return float(score_text)
        except:
            return 0.5  # Default to neutral if parsing fails
    
    def fetch_and_filter_articles(self) -> list[dict]:
        """Fetch articles and filter by positivity threshold."""
        
        api_key = os.getenv("NEWS_API_KEY", "demo")
        url = "https://newsapi.org/v2/everything"
        
        params = {
            "q": self.config["topic"],
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": 10,  # Fetch more to filter down
            "apiKey": api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            articles = response.json().get("articles", [])
            
            # Transform articles
            transformed = []
            for article in articles:
                a = {
                    "title": article["title"],
                    "description": article["description"],
                    "url": article["url"],
                    "source": article["source"]["name"],
                    "published": article["publishedAt"][:10]
                }
                
                # Assess sentiment
                print(f"  Assessing: {a['title'][:50]}...")
                a["sentiment_score"] = self.assess_article_sentiment(a)
                transformed.append(a)
            
            # Filter by positivity threshold
            threshold = self.config.get("positivity_threshold", 0.4)
            filtered = [a for a in transformed if a["sentiment_score"] >= threshold]
            
            print(f"  Kept {len(filtered)}/{len(articles)} articles (threshold: {threshold})")
            return filtered
        
        except Exception as e:
            print(f"Error fetching articles: {e}")
            return []
    
    def synthesize_brief(self, articles: list[dict]) -> str:
        """Create the morning brief from filtered articles."""
        
        if not articles:
            return f"No constructive news about {self.config['topic']} today. Sometimes silence is golden!"
        
        articles_text = "\n".join([
            f"- {a['title']} (Score: {a['sentiment_score']:.1f})\n  {a['description']}"
            for a in articles
        ])
        
        prompt = f"""You are a morning news curator focused on constructive optimism.
Synthesize these articles about {self.config['topic']} into a SHORT (2-3 sentences), POSITIVE morning brief.

IMPORTANT: These articles have already been filtered for constructiveness, so lean into the progress.
- Highlight key trends and opportunities
- What's changing in {self.config['topic']}?
- Why should someone in this field care TODAY?
- End with: "Today's focus: [one actionable insight]"

Keep it under 150 words.

Articles:
{articles_text}

Write the brief:"""
        
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return message.content[0].text
    
    def send_email(self, brief_html: str):
        """Send the brief via email using SMTP."""
        
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")
        recipient_email = self.config["email_to"]
        
        if not all([sender_email, sender_password]):
            print("⚠️  Email not configured. Skipping email delivery.")
            print("   Set SENDER_EMAIL and SENDER_PASSWORD env vars")
            return False
        
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = f"☀️ Your {self.config['topic'].title()} Morning Brief"
            message["From"] = sender_email
            message["To"] = recipient_email
            
            message.attach(MIMEText(brief_html, "html"))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, message.as_string())
            
            print(f"✓ Email sent to {recipient_email}")
            return True
        
        except Exception as e:
            print(f"✗ Email failed: {e}")
            return False
    
    def generate_html(self, brief_text: str, articles: list[dict]) -> str:
        """Generate HTML version of the brief."""
        
        articles_html = "\n".join([
            f"""
            <div style="margin: 12px 0; padding: 12px; border-left: 3px solid #10b981; background: #f0fdf4;">
                <p style="margin: 0; font-weight: bold;"><a href="{a['url']}" style="color: #059669; text-decoration: none;">{a['title']}</a></p>
                <p style="margin: 6px 0 0 0; font-size: 12px; color: #666;">{a['source']} · {a['published']} · Optimism Score: {a['sentiment_score']:.1%}</p>
            </div>
            """
            for a in articles[:3]
        ])
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333; }}
                .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 24px; border-radius: 8px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 8px 0 0 0; opacity: 0.95; }}
                .brief {{ background: #ecfdf5; padding: 20px; border-radius: 6px; margin: 20px 0; line-height: 1.6; border: 1px solid #d1fae5; }}
                .footer {{ font-size: 12px; color: #999; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 20px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>☀️ Morning Brief</h1>
                <p>{self.config['topic'].title()}</p>
                <p style="font-size: 12px; margin: 12px 0 0 0;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
            
            <div class="brief">
                {brief_text}
            </div>
            
            <h3>📰 Today's Sources</h3>
            {articles_html}
            
            <div class="footer">
                <p><strong>Your Information Diet:</strong> Curated for learning, not doomscrolling.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def run_morning_briefing(self):
        """Execute the full morning briefing pipeline."""
        
        print(f"\n{'='*60}")
        print(f"🌅 Morning Briefing: {self.config['topic'].upper()}")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        print("📰 Fetching and filtering articles...")
        articles = self.fetch_and_filter_articles()
        
        if articles:
            print(f"\n🤖 Synthesizing brief...")
            brief = self.synthesize_brief(articles)
            
            print(f"\n{brief}\n")
            
            html = self.generate_html(brief, articles)
            
            # Save to file
            with open("morning_brief.html", "w") as f:
                f.write(html)
            print("✓ HTML saved to morning_brief.html")
            
            # Try to send email
            self.send_email(html)
        
        else:
            print("No constructive articles found today. Take a break!")
    
    def schedule(self):
        """Start the background scheduler."""
        
        schedule_time = self.config.get("schedule_time", "07:30")
        
        self.scheduler.add_job(
            self.run_morning_briefing,
            "cron",
            hour=int(schedule_time.split(":")[0]),
            minute=int(schedule_time.split(":")[1]),
            id="morning_briefing"
        )
        
        self.scheduler.start()
        print(f"✓ Scheduled daily briefing at {schedule_time}")
        print("  (Press Ctrl+C to stop)\n")
        
        # Keep scheduler running
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.scheduler.shutdown()
            print("✓ Scheduler stopped")


def main():
    """Run the agent."""
    
    config = {
        "topic": "climate technology",
        "schedule_time": "07:30",
        "email_to": "you@example.com",  # Change this
        "positivity_threshold": 0.4  # 0-1 scale
    }
    
    agent = MorningNewsAgent(config)
    
    # For testing, run once immediately instead of waiting for schedule
    print("Running one-off briefing (not scheduled)\n")
    agent.run_morning_briefing()
    
    # To enable scheduling, uncomment:
    # agent.schedule()


if __name__ == "__main__":
    main()