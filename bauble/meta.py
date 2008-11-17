#
# meta.py
#
from sqlalchemy import *

import bauble
import bauble.db as db
from bauble.utils.log import debug

VERSION_KEY = u'version'
CREATED_KEY = u'created'
REGISTRY_KEY = u'registry'

# date format strings:
# yy - short year
# yyyy - long year
# dd - number day, always two digits
# d - number day, two digits when necessary
# mm -number month, always two digits
# m - number month, two digits when necessary
DATE_FORMAT_KEY = u'date_format'

def get_default(name, default=None, session=None):
    if not session:
        session = bauble.Session()
    query = session.query(BaubleMeta)
    meta = query.filter_by(name=name).first()
    if not meta:
        meta = BaubleMeta(name=name, value=default)
    return meta


class BaubleMeta(db.Base):
    __tablename__ = 'bauble'
    name = Column(Unicode(64), unique=True)
    value = Column(UnicodeText)

