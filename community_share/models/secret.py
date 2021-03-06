from datetime import datetime, timedelta
import string, random, json

from typing import Any, Dict, Optional

from sqlalchemy import Column, String, DateTime, Boolean

from community_share import Base, Store, with_store


class Secret(Base):
    __tablename__ = 'secret'
    KEY_LENGTH = 200

    key = Column(String(KEY_LENGTH), primary_key=True)
    info = Column(String)
    expiration = Column(DateTime, default=datetime.utcnow)
    used = Column(Boolean, default=False)

    @classmethod
    def make_key(cls, key_length=KEY_LENGTH):
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
        key = ''.join(random.choice(chars) for _ in range(cls.KEY_LENGTH))
        return key

    @classmethod
    def make(cls, info, hours_duration):
        info_as_json = json.dumps(info)
        key = cls.make_key()
        expiration = datetime.now() + timedelta(hours=hours_duration)
        secret = Secret(key=key, info=info_as_json, expiration=expiration)
        return secret

    def get_info(self):
        info = None
        try:
            info = json.loads(self.info)
        except ValueError:
            logger.error("Invalid JSON data in secret.info")
        return info


@with_store
def create_secret(info: Dict[str, Any], hours_duration: int, store: Store=None) -> Secret:
    secret = Secret.make(info, hours_duration)
    store.session.add(secret)
    store.session.commit()
    return secret


@with_store
def lookup_secret(key: str, store: Store=None) -> Optional[Secret]:
    secret = store.session.query(Secret)
    secret = secret.filter(Secret.key == key)
    secret = secret.filter(Secret.used == False)
    secret = secret.filter(Secret.expiration > datetime.utcnow())
    return secret.first()
