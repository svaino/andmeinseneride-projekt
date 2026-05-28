import os

SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URI"]
SECRET_KEY = os.environ["SECRET_KEY"]

# Redis puudub -- kasutatakse lihtsat malusisu vahemalu
CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache"}
FILTER_STATE_CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache"}
EXPLORE_FORM_DATA_CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache"}

FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
}

WTF_CSRF_ENABLED = True