import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from config import BREVO_API_KEY, BREVO_SENDER_EMAIL
from id_generator import generate_application_id


configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = BREVO_API_KEY

api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
    sib_api_v3_sdk.ApiClient(configuration)
)


def send_email(candidate_name, candidate_email, decision):
    application_id = generate_application_id()

    if decision.lower() == "shortlisted":

        subject = f"Vtab Square Recruitment | Application ID: {application_id}"

        html_content = f"""
        <html>
        <body>
            <h2>Congratulations, {candidate_name}! 🎉</h2>

            <p>We are pleased to inform you that you have been <b>Shortlisted</b>
            for the next stage of our recruitment process.</p>

            <p>Our AI Recruitment System has successfully evaluated your resume.</p>

            <p>We will soon contact you with your interview schedule.</p>
            <p><b>Application ID:</b> {application_id}</p>
            <p>Please reply to this email. Keep your Application ID in the conversation for faster processing.</p>

            <br>

            <p>Regards,<br>
            <b>VTAB Square Recruitment Team</b></p>
        </body>
        </html>
        """

    else:

        subject = "Application Status Update"

        html_content = f"""
        <html>
        <body>

            <h2>Hello {candidate_name},</h2>

            <p>Thank you for applying to VTAB Square.</p>

            <p>After carefully reviewing your resume,
            we regret to inform you that you have <b>not been shortlisted</b>
            for this opportunity.</p>

            <p>We appreciate your interest and encourage you
            to apply again in the future.</p>

            <br>

            <p>Regards,<br>
            <b>VTAB Square Recruitment Team</b></p>

        </body>
        </html>
        """

    email = sib_api_v3_sdk.SendSmtpEmail(

        to=[{"email": candidate_email, "name": candidate_name}],

        sender={
            "email": BREVO_SENDER_EMAIL,
            "name": "VTAB Square Recruitment"
        },

        subject=subject,

        html_content=html_content

    )

    try:

        api_instance.send_transac_email(email)

        print("✅ Email Sent Successfully!")

    except ApiException as e:

        print(e)