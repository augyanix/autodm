# Privacy Policy — @augyanix Auto-DM

**Last updated:** 1 November 2026
**Operator:** Maadhava Rao (Learn AI), India
**Contact:** [augyanix@gmail.com](mailto:augyanix@gmail.com)

## What the bot does
When you comment a keyword on an @augyanix Instagram post, our bot sends you a DM with a link. Some posts ask you to follow @augyanix first; the bot then checks whether you follow before sending the link.

## Data we process
We receive data only through Meta's official Instagram API:
- Your Instagram-scoped user ID.
- Your comment ID and comment text, to find the keyword.
- The matched keyword and a timestamp.
- Whether you follow @augyanix, when a follow check is needed.
- The content of a DM you send us, only to trigger the follow check.

We do **not** store comment text, DM content or your follow status.

## What we store, and for how long
Stored in Google Cloud Firestore (Mumbai region, India):
- **"Already replied" record:** comment ID, matched keyword, time. No user ID. Deleted automatically after 8 days.
- **"Waiting for follow check" record:** your Instagram-scoped user ID, the reply we will send, time. Deleted automatically after 24 hours, or as soon as the link is sent.

Automatic deletion can take a little extra time to complete. These periods cover only our bot's records, not comments or messages kept by Instagram. Our logs do not contain user IDs, comments or messages.

## Why we process it
To answer your request, check a stated follow requirement, and avoid sending you duplicate messages. Never for advertising or unrelated marketing. Where GDPR applies, we rely on our legitimate interest in fulfilling the interaction you started, subject to your rights.

## Sharing
We do not sell your data or use it for ads. Our only service providers for this bot are Meta (Instagram API) and Google Cloud (hosting), whose processing is also subject to their own privacy terms. Data is stored in India; these providers may process it in other countries under their legal safeguards.

## Data deletion instructions
1. Email [augyanix@gmail.com](mailto:augyanix@gmail.com) with the subject "Instagram bot data deletion", or DM @augyanix.
2. Include your Instagram username and ask us to delete your bot data.
3. We may ask you to confirm from that Instagram account. Never send your password.

We delete the records we hold and confirm when done. This does not delete your Instagram comments, conversations, or data held by Meta.

## Your rights
You can contact us to request access, correction or deletion, to object to processing, or to raise a complaint. Depending on where you live, you may have further rights, including complaining to a data-protection authority. We respond within the time the law requires.

## Children
The bot is not directed at anyone under 18. Contact us if you believe a child's data was processed and we will delete it.

## Changes and source code
We update this page when our practices change. Source code: [github.com/augyanix/autodm](https://github.com/augyanix/autodm)
