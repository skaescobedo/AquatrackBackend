# services/email_service.py
"""
Servicio de envío de emails usando Gmail SMTP.
Si las credenciales no están configuradas, imprime en logs (modo desarrollo).
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.settings import settings


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Envía un email usando Gmail SMTP.

    Args:
        to_email: Email del destinatario
        subject: Asunto del email
        html_body: Cuerpo del email en HTML

    Returns:
        True si se envió correctamente, False si falló
    """
    # Si no hay configuración de email, imprimir en consola (desarrollo)
    if not settings.MAIL_USER or not settings.MAIL_PASS:
        print("=" * 80)
        print("📧 EMAIL (MODO DESARROLLO - No se envió email real)")
        print("=" * 80)
        print(f"Para: {to_email}")
        print(f"Asunto: {subject}")
        print("-" * 80)
        print(html_body)
        print("=" * 80)
        return True

    try:
        # Configurar mensaje
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Agregar cuerpo HTML
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)

        # Conectar a Gmail SMTP
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(settings.MAIL_USER, settings.MAIL_PASS)
            server.send_message(msg)

        print(f"✅ Email enviado exitosamente a {to_email}")
        return True

    except Exception as e:
        print(f"❌ Error al enviar email a {to_email}: {str(e)}")
        return False


def send_password_reset_email(to_email: str, reset_link: str, user_name: str) -> bool:
    """
    Envía email de recuperación de contraseña.

    Args:
        to_email: Email del usuario
        reset_link: URL completo para resetear contraseña
        user_name: Nombre del usuario

    Returns:
        True si se envió correctamente
    """
    subject = "Recuperación de contraseña - AquaTrack"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #0077be; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 30px; background-color: #f9f9f9; }}
            .button {{ 
                display: inline-block; 
                padding: 12px 30px; 
                background-color: #0077be; 
                color: white; 
                text-decoration: none; 
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
            .warning {{ color: #d9534f; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔒 Recuperación de Contraseña</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{user_name}</strong>,</p>

                <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta en AquaTrack.</p>

                <p>Haz clic en el siguiente botón para crear una nueva contraseña:</p>

                <div style="text-align: center;">
                    <a href="{reset_link}" class="button">Restablecer Contraseña</a>
                </div>

                <p>O copia y pega este enlace en tu navegador:</p>
                <p style="word-break: break-all; background-color: #eee; padding: 10px;">
                    {reset_link}
                </p>

                <p class="warning">⚠️ Este enlace expirará en {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutos.</p>

                <hr>

                <p><strong>¿No solicitaste este cambio?</strong></p>
                <p>Si no solicitaste restablecer tu contraseña, puedes ignorar este correo de forma segura. 
                Tu contraseña no será cambiada.</p>
            </div>
            <div class="footer">
                <p>Este es un correo automático, por favor no responder.</p>
                <p>&copy; 2025 AquaTrack. Todos los derechos reservados.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(to_email, subject, html_body)