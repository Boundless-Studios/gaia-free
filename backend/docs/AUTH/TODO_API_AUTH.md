1)  Should the admin endpoints have more explicit permissions vs other endpoints? Is that part of the implementation happening later?     

2) Verify that there's no security gaps or insecure implementation 

3) Confirm that all API endpoints that we expose are secured by the Oauth.Require the Access Token: Design all backend endpoints to expect an access token in the Authorization header (usually as a Bearer token), and immediately reject any request missing this header.

4) Do we have our Database allowlist

5) Do we need Token Introspection? For non-JWT tokens, call the OAuth2 provider’s introspection endpoint to check token validity. 

6) Fail Securely: Never process unauthenticated or unauthorized requests; always return an appropriate error response if token checks fail.

7) Do we have token validation?

8) Can we run tests to confirm we can't access components when we're not oauthed


9) I see errors: gaia-postgres      | 2025-08-27 05:13:41.179 UTC [706] FATAL:  role "gaia_user" does not exist
gaia-postgres      | 2025-08-27 05:13:44.939 UTC [713] FATAL:  role "postgres" does not exist
gaia-backend-gpu   | 2025-08-27 05:14:04,154 - auth.src.jwt_handler - WARNING - JWT decode error: Not enough segments
  