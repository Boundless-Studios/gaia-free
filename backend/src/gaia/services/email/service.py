"""
Email service implementation with support for multiple providers.
"""

import os
import logging
from typing import Optional, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    """Abstract base class for email providers"""

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML version of email content
            text_content: Plain text version (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        pass


class SMTPEmailProvider(EmailProvider):
    """SMTP email provider using Python's built-in smtplib"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
        from_name: str = "Gaia",
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.from_name = from_name
        self.use_tls = use_tls

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email

            # Add plain text and HTML parts
            if text_content:
                part1 = MIMEText(text_content, "plain")
                msg.attach(part1)

            part2 = MIMEText(html_content, "html")
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email} via SMTP")
            return True

        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}", exc_info=True)
            return False


class ConsoleEmailProvider(EmailProvider):
    """Development email provider that logs emails to console"""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Log email to console instead of sending"""
        logger.info("=" * 80)
        logger.info("📧 CONSOLE EMAIL (Development Mode)")
        logger.info("=" * 80)
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info("-" * 80)
        logger.info("Content:")
        logger.info(text_content if text_content else html_content)
        logger.info("=" * 80)
        return True


class EmailService:
    """
    Email service that manages email providers and sending.

    Supports multiple providers with automatic fallback.
    """

    def __init__(self, provider: EmailProvider):
        self.provider = provider

    async def send_welcome_email(self, to_email: str, display_name: str) -> bool:
        """Send welcome email after user opts in during registration"""
        subject = "🔒 Welcome to GAIA Private Alpha - NDA Reminder"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                           color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .alpha-badge {{ display: inline-block; background: #ff6b6b; color: white; padding: 6px 15px;
                               border-radius: 15px; font-weight: bold; font-size: 12px; margin-bottom: 10px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .warning-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;
                               margin: 20px 0; border-radius: 5px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea;
                          color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="alpha-badge">🔒 PRIVATE ALPHA</div>
                    <h1>Welcome to GAIA!</h1>
                </div>
                <div class="content">
                    <h2>Hello {display_name},</h2>
                    <p>Thank you for joining the GAIA private alpha! We're excited to have you as a playtester.</p>

                    <div class="warning-box">
                        <strong>⚠️ NDA Reminder - Confidential Information</strong>
                        <p style="margin: 10px 0 0 0;">
                            You have accepted an NDA. Please remember:
                        </p>
                        <ul style="margin: 10px 0 0 0;">
                            <li><strong>DO NOT</strong> stream, record, or share screenshots</li>
                            <li><strong>DO NOT</strong> discuss game details publicly</li>
                            <li>All content is confidential and for playtesting only</li>
                        </ul>
                    </div>

                    <p><strong>What to Expect:</strong></p>
                    <ul>
                        <li><strong>AI Dungeon Master:</strong> Experience AI-powered storytelling</li>
                        <li><strong>Character Creation:</strong> Build unique characters</li>
                        <li><strong>Multiplayer:</strong> Play with other playtesters</li>
                        <li><strong>Bugs & Issues:</strong> Help us identify and fix issues</li>
                    </ul>

                    <p style="text-align: center;">
                        <a href="https://gaia-rpg.com" class="button">Start Playtesting</a>
                    </p>

                    <p><strong>Important:</strong> Please report any bugs, issues, or feedback through the in-game system or by replying to this email.</p>

                    <p>Thank you for being part of our alpha testing program!</p>
                    <p><strong>The Boundless Studios Team</strong></p>
                </div>
                <div class="footer">
                    <p>🔒 This is a private alpha - All content is confidential</p>
                    <p>© 2025 Boundless Studios. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
🔒 PRIVATE ALPHA - Welcome to GAIA!

Hello {display_name},

Thank you for joining the GAIA private alpha! We're excited to have you as a playtester.

⚠️ NDA REMINDER - CONFIDENTIAL INFORMATION
You have accepted an NDA. Please remember:
- DO NOT stream, record, or share screenshots
- DO NOT discuss game details publicly
- All content is confidential and for playtesting only

What to Expect:
- AI Dungeon Master: Experience AI-powered storytelling
- Character Creation: Build unique characters
- Multiplayer: Play with other playtesters
- Bugs & Issues: Help us identify and fix issues

Start playtesting at: https://gaia-rpg.com

IMPORTANT: Please report any bugs, issues, or feedback through the in-game system or by replying to this email.

Thank you for being part of our alpha testing program!
The Boundless Studios Team

---
🔒 This is a private alpha - All content is confidential
© 2025 Boundless Studios. All rights reserved.
        """

        return await self.provider.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

    async def send_registration_complete_email(
        self, to_email: str, display_name: str
    ) -> bool:
        """Send email confirming registration is complete"""
        subject = "✅ Alpha Access Granted - GAIA Playtester Agreement Accepted"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                           color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .alpha-badge {{ display: inline-block; background: #ff6b6b; color: white; padding: 6px 15px;
                               border-radius: 15px; font-weight: bold; font-size: 12px; margin-bottom: 10px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .success-icon {{ font-size: 64px; text-align: center; margin: 20px 0; }}
                .warning-box {{ background: #fff5f5; border-left: 4px solid #ff6b6b; padding: 15px;
                               margin: 20px 0; border-radius: 5px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea;
                          color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="alpha-badge">🔒 PRIVATE ALPHA</div>
                    <h1>Registration Complete!</h1>
                </div>
                <div class="content">
                    <div class="success-icon">✅</div>
                    <h2>Hello {display_name},</h2>
                    <p>You have successfully accepted the GAIA Playtester Agreement and now have access to the private alpha!</p>

                    <div class="warning-box">
                        <strong>🔒 Remember Your NDA Obligations:</strong>
                        <ul style="margin: 10px 0 0 0;">
                            <li>All game content is <strong>confidential</strong></li>
                            <li><strong>No streaming, recording, or screenshots</strong> without permission</li>
                            <li><strong>No public discussion</strong> of game details</li>
                            <li>Violations may result in access termination</li>
                        </ul>
                    </div>

                    <p><strong>You can now:</strong></p>
                    <ul>
                        <li>Access the AI Dungeon Master</li>
                        <li>Create and test characters</li>
                        <li>Join multiplayer campaigns</li>
                        <li>Provide valuable feedback</li>
                    </ul>

                    <p style="text-align: center;">
                        <a href="https://gaia-rpg.com" class="button">Start Playtesting Now</a>
                    </p>

                    <p><strong>How to Help:</strong></p>
                    <ul>
                        <li>Report bugs through the in-game system</li>
                        <li>Share your feedback and suggestions</li>
                        <li>Document any issues you encounter</li>
                        <li>Help us make GAIA better!</li>
                    </ul>

                    <p>Thank you for being part of our alpha testing program. Your feedback is invaluable!</p>

                    <p>Best regards,</p>
                    <p><strong>The Boundless Studios Team</strong></p>
                </div>
                <div class="footer">
                    <p>🔒 This is a private alpha - All content is confidential</p>
                    <p>© 2025 Boundless Studios. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
✅ ALPHA ACCESS GRANTED

Hello {display_name},

You have successfully accepted the GAIA Playtester Agreement and now have access to the private alpha!

🔒 REMEMBER YOUR NDA OBLIGATIONS:
- All game content is CONFIDENTIAL
- NO streaming, recording, or screenshots without permission
- NO public discussion of game details
- Violations may result in access termination

You can now:
- Access the AI Dungeon Master
- Create and test characters
- Join multiplayer campaigns
- Provide valuable feedback

Start playtesting at: https://gaia-rpg.com

How to Help:
- Report bugs through the in-game system
- Share your feedback and suggestions
- Document any issues you encounter
- Help us make GAIA better!

Thank you for being part of our alpha testing program. Your feedback is invaluable!

Best regards,
The Boundless Studios Team

---
🔒 This is a private alpha - All content is confidential
© 2025 Boundless Studios. All rights reserved.
        """

        return await self.provider.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

    async def send_access_request_submitted_email(
        self, to_email: str, display_name: str
    ) -> bool:
        """Send email to user confirming their access request was submitted"""
        subject = "🔐 GAIA Access Request Submitted"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                           color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .alpha-badge {{ display: inline-block; background: #ff6b6b; color: white; padding: 6px 15px;
                               border-radius: 15px; font-weight: bold; font-size: 12px; margin-bottom: 10px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 15px;
                             margin: 20px 0; border-radius: 5px; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="alpha-badge">🔒 PRIVATE ALPHA</div>
                    <h1>Access Request Received</h1>
                </div>
                <div class="content">
                    <h2>Hello {display_name},</h2>
                    <p>Thank you for your interest in GAIA! We've received your access request.</p>

                    <div class="info-box">
                        <strong>📋 What happens next?</strong>
                        <ul style="margin: 10px 0 0 0;">
                            <li>Your request has been submitted to our admin team</li>
                            <li>We will review your request and get back to you</li>
                            <li>You'll receive an email once your access is approved</li>
                        </ul>
                    </div>

                    <p>In the meantime, please note that you've accepted the Playtester Agreement which includes an NDA. All information about GAIA remains confidential.</p>

                    <p>Thank you for your patience!</p>
                    <p><strong>The Boundless Studios Team</strong></p>
                </div>
                <div class="footer">
                    <p>🔒 This is a private alpha - All content is confidential</p>
                    <p>© 2025 Boundless Studios. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
🔐 GAIA ACCESS REQUEST RECEIVED

Hello {display_name},

Thank you for your interest in GAIA! We've received your access request.

WHAT HAPPENS NEXT?
- Your request has been submitted to our admin team
- We will review your request and get back to you
- You'll receive an email once your access is approved

In the meantime, please note that you've accepted the Playtester Agreement which includes an NDA. All information about GAIA remains confidential.

Thank you for your patience!
The Boundless Studios Team

---
🔒 This is a private alpha - All content is confidential
© 2025 Boundless Studios. All rights reserved.
        """

        return await self.provider.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

    async def send_access_request_email(
        self,
        admin_email: str,
        user_email: str,
        display_name: str,
        reason: Optional[str] = None
    ) -> bool:
        """Send access request notification to admin"""
        subject = f"🔐 GAIA Access Request from {user_email}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                           color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 15px;
                             margin: 20px 0; border-radius: 5px; }}
                .user-info {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 New Access Request</h1>
                </div>
                <div class="content">
                    <p>A new user has requested access to the GAIA private alpha:</p>

                    <div class="user-info">
                        <p><strong>User Email:</strong> {user_email}</p>
                        <p><strong>Display Name:</strong> {display_name}</p>
                        <p><strong>EULA Status:</strong> Accepted</p>
                        {f'<p><strong>Reason:</strong> {reason}</p>' if reason else ''}
                    </div>

                    <div class="info-box">
                        <strong>Next Steps:</strong>
                        <ol style="margin: 10px 0 0 0;">
                            <li>Review the user request</li>
                            <li>If approved, add them to the allowlist using the admin DB script</li>
                            <li>User will receive automatic email notification once added</li>
                        </ol>
                    </div>

                    <p><strong>To approve this user:</strong></p>
                    <pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto;">
# From the gaia repository root:
python3 scripts/user_management/add_production_user.py \\
  {user_email} \\
  {user_email.split('@')[0]} \\
  "{display_name}"
                    </pre>

                    <p>The user is currently seeing a "waiting for approval" screen and cannot access the application until you grant access.</p>
                </div>
                <div class="footer">
                    <p>GAIA Admin Notification System</p>
                    <p>© 2025 Boundless Studios</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
🔐 NEW GAIA ACCESS REQUEST

A new user has requested access to the GAIA private alpha:

User Email: {user_email}
Display Name: {display_name}
EULA Status: Accepted
{f'Reason: {reason}' if reason else ''}

NEXT STEPS:
1. Review the user request
2. If approved, add them to the allowlist using the admin DB script
3. User will receive automatic email notification once added

TO APPROVE THIS USER:
# From the gaia repository root:
python3 scripts/user_management/add_production_user.py \\
  {user_email} \\
  {user_email.split('@')[0]} \\
  "{display_name}"

The user is currently seeing a "waiting for approval" screen and cannot access the application until you grant access.

---
GAIA Admin Notification System
© 2025 Boundless Studios
        """

        return await self.provider.send_email(
            to_email=admin_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )


_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """
    Get or create the email service singleton.

    Returns:
        EmailService instance configured based on environment
    """
    global _email_service

    if _email_service is not None:
        return _email_service

    # Check environment configuration
    email_provider = os.getenv("EMAIL_PROVIDER", "console").lower()

    if email_provider == "smtp":
        # Use SMTP provider
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("EMAIL_FROM_ADDRESS", "noreply@gaia-rpg.com")
        from_name = os.getenv("EMAIL_FROM_NAME", "Gaia")

        if not all([smtp_host, smtp_user, smtp_password]):
            logger.warning(
                "SMTP credentials not fully configured, falling back to console email"
            )
            provider = ConsoleEmailProvider()
        else:
            logger.info(f"Using SMTP email provider: {smtp_host}:{smtp_port}")
            provider = SMTPEmailProvider(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                from_email=from_email,
                from_name=from_name,
                use_tls=True,
            )
    else:
        # Development: Use console logging
        logger.info("Using console email provider for development")
        provider = ConsoleEmailProvider()

    _email_service = EmailService(provider=provider)
    return _email_service
