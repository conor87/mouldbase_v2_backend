# Auth-enabled FastAPI

## New features
- `users` table with fields: `id`, `username`, `email`, `hashed_password`, `is_active`.
- Registration endpoint: `POST /auth/register`
- Login endpoint: `POST /auth/token` (OAuth2 Password flow) → returns JWT
- Protected endpoints: all in `/companies` and `/orders_positions` now require a Bearer token.

## Quick start
Install extras:
```
pip install python-jose[cryptography] passlib[bcrypt] python-multipart
```
Set a strong secret in `routers/auth.py`:
```python
SECRET_KEY = "CHANGE_ME_SUPER_SECRET_KEY"
```

### Register a user
```
POST /auth/register
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "S3cretPass!"
}
```

### Obtain a token
```
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=alice&password=S3cretPass!
```
Response:
```json
{"access_token":"...","token_type":"bearer"}
```

### Use protected endpoints
Add header:
```
Authorization: Bearer <access_token>
```
