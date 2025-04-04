import datetime as dt
from typing import Dict, List, Optional, Union, Text, Tuple, Literal
from pydantic import BaseModel, EmailStr, Field
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status, APIRouter
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel, OAuthFlowPassword
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2, OAuth2PasswordRequestForm
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.templating import Jinja2Templates
#from jose import JWTError, jwt, ExpiredSignatureError
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.handlers.sha2_crypt import sha512_crypt as crypto
from passlib.context import CryptContext
from pydantic import BaseModel
import sqlite3
from pathlib import Path
import string
import secrets
from environs import Env
import hashlib

p = Path(__file__).parent.resolve()
static_path = p / "static/"
p = p / "dbfiles"

env = Env()
env.read_env()

class Settings:
    SECRET_KEY = env('SETTINGS_AUTH_SECRET_KEY')
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    COOKIE_NAME: Literal['access_token'] = 'access_token'
    
settings = Settings()

# SSD_CLASS = {"ssd_config": ["1", "2", "3"]}
# enum = Enum("enum", {str(i):i for i in appconfig['projectsids']})

# @dataclass
# class ScheduleModel:
#     ids_in: Optional[List[enum]] = Query(None)

class CopiaSaggio(BaseModel):
    rowid: int 
    uni_cod: str | None = None
    facolta: str | None = None
    materia_ssd_cod: str | None = None
    materia_nome: str | None = None
    insegnamento_prof: str | None = None
    insegnamento_prof_www: str | None = None
    prof_id: int | None = None
    insegnamento_id: int | None = None
    email: str | None = None
    indirizzo: str | None = None
    citta: str | None = None
    telefono: str | None = None
    note: str | None = None
    isbn: str | None = None
    titolo: str | None = None
    data: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: EmailStr

class User(BaseModel):
    id: int
    username: EmailStr
    is_active: str | None = None
    tenant_id: str | None = None
    is_admin: int | None = None

class UserInDB(User):
    hashed_password: str
    
class OAuth2PasswordBearerWithCookie(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: Optional[str] = None,
        scopes: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlowsModel(password=OAuthFlowPassword(tokenUrl=tokenUrl, scopes=scopes))
        super().__init__(
            flows=flows,
            scheme_name=scheme_name,
            description=description,
            auto_error=auto_error,
        )

    async def __call__(self, request: Request) -> Optional[str]:
        # IMPORTANT: this is the line that differs from FastAPI. Here we use 
        # `request.cookies.get(settings.COOKIE_NAME)` instead of 
        # `request.headers.get("Authorization")`
        authorization: Optional[str] = request.cookies.get(settings.COOKIE_NAME)
        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        return param


oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_random_passw():
    alphabet = string.ascii_letters + string.digits
    while True:
        password = ''.join(secrets.choice(alphabet) for i in range(10))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and sum(c.isdigit() for c in password) >= 3):
            break
    return password

    
def update_passw_user(user: str, passw: str, tenant_id: str):
    with sqlite3.connect(p/'shared.db') as conn:
        conn.execute("UPDATE users SET hashed_password = ? WHERE username = ? AND tenant_id = ?", 
                     (get_password_hash(passw), user, tenant_id))
        conn.commit()
    return True



def get_user(username: str):
    with sqlite3.connect(p/'shared.db') as conn:
        conn.row_factory = sqlite3.Row
        res = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        res = res.fetchone()
    return res

def create_access_token(data: Dict) -> str:
    to_encode = data.copy()
    expire = dt.datetime.now() + dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def authenticate_user(username: str, plain_password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(plain_password, user['hashed_password']): # type ignore
        return False
    return user


def decode_token(token: str) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="Could not validate credentials."
    )
    token = token.removeprefix("Bearer").strip()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("username")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise HTTPException(status_code=403, detail="token has been expired")
    # except JWTError as e:
    #     print(e)
    #     raise credentials_exception
    user = get_user(username)
    if user is None:
        raise credentials_exception
    return user


def get_current_user_from_token(token: str = Depends(oauth2_scheme)) -> User:
    """
    Get the current user from the cookies in a request.
    Use this function when you want to lock down a route so that only 
    authenticated users can see access the route.
    """
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = decode_token(token)
    return user


def get_current_user_from_cookie(request: Request) -> User:
    """
    Get the current user from the cookies in a request.
    Use this function from inside other routes to get the current user. Good
    for views that should work for both logged in, and not logged in users.
    """
    token = request.cookies.get(settings.COOKIE_NAME)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = decode_token(token)
    return user

def get_tenant_hash(user: User = Depends(get_current_user_from_token)):
    return hashlib.md5(f'{user['tenant_id']}'.encode('utf-8')).hexdigest() # type: ignore
