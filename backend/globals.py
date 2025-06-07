from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache

cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
db = SQLAlchemy()