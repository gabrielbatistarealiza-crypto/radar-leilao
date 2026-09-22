from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.security.token import SECRET_KEY, ALGORITHM

security = HTTPBearer()

def usuario_logado(
        credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials

    print("TOKEN:", token)

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        print("PAYLOAD:", payload)

        return payload

    except JWTError as e:

        print("ERRO JWT:", repr(e))

        raise HTTPException(
            status_code=401,
            detail="Token invalido."
        )
