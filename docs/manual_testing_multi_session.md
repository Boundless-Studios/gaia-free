# Multi-Session Frontend Verification Playbook

Use this checklist in staging/preview builds of the React app. These steps assume you are signed in with two different Auth0 accounts (Owner and Guest) in separate browsers or profiles.

## 1. Session Creation & Persistence
- Sign in as **Owner** and open the app.
- Click `🎲 New Campaign` to create a fresh session.
- Observe the chat area for the welcome or blank-campaign message.
- Confirm the session id is shown under “Campaign:” in the chat header and persisted in `localStorage` (`lastCampaignId`).

## 2. Share Flow (Owner)
- With the new campaign selected, click `🤝 Share`.
- Verify the share modal loads a token and a full invite link.
- Click `Copy Link`; ensure a toast/banner appears (“Invite link copied…”).
- Click `Regenerate` and ensure a new token/link is generated.
- Close the modal.

## 3. Join Flow (Guest via Link)
- On a second browser/profile signed in as **Guest**, paste the invite URL into the address bar (or click directly if available).
- The app should redirect to the main view, auto-join the session, and display an info banner (“Successfully joined shared session.”).
- Confirm chat loads the current campaign messages and the campaign id matches the Owner’s.

## 4. Join Flow (Guest via Campaign Manager)
- From the Guest session, open `📋 Campaigns`.
- Paste the same invite token into the “Join Shared Session” panel and click `Join Session`.
- Expect success message in the panel and the modal to close automatically.
- Verify the campaign is now active and accessible for the Guest.

## 5. Membership Enforcement
- Sign in as a third user (**Unauthorized**) and attempt to open the share modal by navigating directly to the invite link.
- The join should fail with an error banner (`Failed to join shared session…`); confirm no session becomes active.

## 6. Automatic Ownership Claim
- Create a campaign as Owner, share the token, and accept it on Guest **before** the Owner presses share again.
- Open the share modal as Owner once more; confirm the token still works (ownership is retained).

## 7. Campaign Autoload
- Refresh both browsers.
- Ensure each account automatically reconnects to the last active campaign (or shows empty state if none).

## 8. Simple Campaign Listing
- Open the campaign manager while logged in as Owner.
- Toggle between “Simple”/“Structured” views and ensure the list reflects membership metadata (owner badge vs member list).

## 9. Regression Smoke
- Chat in the shared session as Owner; ensure messages appear in both browsers in real time.
- Use the Resume button if available; verify it sends a prompt and updates both clients.
- Generate context (`📝 Add Context`) and confirm the history updates for both users.

## 10. Clean Up
- Close extra browsers and log out.
- If this is a staging environment, delete the test campaign via the campaign manager (`Delete`), ensuring it disappears from the list for all users.
