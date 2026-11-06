# WhatsApp setup (Meta WhatsApp Cloud API)

CommuteCircle already sends WhatsApp messages in **mock mode**: every message is recorded
under Student Affairs → **Messages** with status `mock`. Real sending starts as soon as the
settings below are added in Render. Budget in the proposal: about $45 of conversation credits
for the pilot (utility templates in Pakistan are charged per conversation by Meta).

## 1. Create the WhatsApp app (team, ~1 hour + 1–2 days for template approval)
1. Create a **Meta Business** account at business.facebook.com (use the project's details).
2. At developers.facebook.com → **My Apps → Create app → Business**, add the **WhatsApp** product.
3. Add a phone number that is **not** already registered on WhatsApp (a new SIM is easiest),
   and verify it. Note its **Phone number ID**.
4. Create a **permanent access token**: Business Settings → System users → add a system user
   with the WhatsApp app assigned → *Generate token* with `whatsapp_business_messaging`.
   Treat it as a password.
5. In App settings → Basic, copy the **App secret** (used to check incoming webhooks are from Meta).

## 2. Message templates (WhatsApp Manager → Message templates → Create, category **Utility**, language **English**)
| Name | Text |
|---|---|
| `cc_reminder` | Hi {{1}}, your CommuteCircle ride to BIC is today. Plan to arrive by {{2}}. Pickup order: {{3}}. Reply 2 if you're not going. |
| `cc_checkin` | Hi {{1}}, did you reach campus with your circle today? Reply 1 for yes or 2 if you didn't go. |
| `cc_proposal` | Hi {{1}}, {{2}} suggested a CommuteCircle travel circle with you. Open the app to accept or decline within 3 days. |
| `cc_sos` | SOS from {{1}} on CommuteCircle. Route: {{2}}. Date: {{3}}. Please contact them now. BIC Student Affairs has been alerted. |

Names must match exactly. Replies (confirmations, fare amounts) are sent as normal text, which
WhatsApp allows within 24 hours of the student's message.

## 3. Settings in Render (commutecircle → Environment)
| Key | Value |
|---|---|
| `CC_WHATSAPP_TOKEN` | the permanent access token |
| `CC_WHATSAPP_PHONE_ID` | the phone number ID |
| `CC_WHATSAPP_APP_SECRET` | the app secret |
| `CC_WHATSAPP_VERIFY_TOKEN` | any long random text you choose (used once, in step 4) |
| `CC_JOBS_TOKEN` | another long random text (used by the schedule in step 5) |
| `CC_SECURITY_WHATSAPP` | optional: campus security's WhatsApp number, messaged on SOS |
| `CC_SECURITY_PHONE` | optional: campus security's phone, shown on the SOS screen |

## 4. Webhook (Meta → WhatsApp → Configuration)
* Callback URL: `https://commutecircle.onrender.com/api/whatsapp/webhook`
* Verify token: the same text as `CC_WHATSAPP_VERIFY_TOKEN`
* Subscribe to the **messages** field.

## 5. Schedule (GitHub → repository → Settings → Secrets and variables → Actions)
Add `CC_APP_URL` = `https://commutecircle.onrender.com` and `CC_JOBS_TOKEN` (same as in
Render). The **Scheduled jobs** workflow then runs every 15 minutes on weekdays. Run it once
by hand (Actions → Scheduled jobs → Run workflow) to check it returns a JSON summary.

## How it works
* Students opt in on their Account page ("Send me WhatsApp reminders and daily check-ins").
* 30–60 minutes before the circle's arrival time: `cc_reminder`.
* After arrival time (until 18:30): `cc_checkin`, if nobody has confirmed the trip yet.
* Replies: **1** confirms the trip for the circle, **2** marks "didn't go", a number records
  your fare share (if you confirmed), **skip** skips the fare, **STOP** turns messages off.
* Each message is sent at most once per student per day; every message is in the Messages tab.
