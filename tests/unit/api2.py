from haas import api, model
from moc.rest import req_local
from schema import Schema, Use, And
from sqlalchemy import create_engine
from uuid import UUID
from werkzeug.local import release_local
import json
import pytest


@pytest.yield_fixture
def setup_db():
    engine = create_engine("sqlite:///:memory:")
    model.Base.metadata.create_all(engine)
    model.Session.configure(bind=engine)
    req_local.db = model.Session()
    yield
    release_local(req_local)

pytestmark = pytest.mark.usefixtures("setup_db")


@pytest.mark.parametrize('typ,input,output', [

    # A node with no nics:
    ('node',

        {
            "ipmi": {
                "host": "ipmi.node4.example.com",
                "user": "alice",
                "pass": "secret",
            },
        },

        {
            "uuid": Use(UUID),
            "free": True,
            "ipmi": {
                "host": "ipmi.node4.example.com",
                "user": "alice",
                "pass": "secret",
            },
        }),

    # A node with one nic
    ('node',

        {
            "ipmi": {
                "host": "ipmi.node4.example.com",
                "user": "alice",
                "pass": "secret",
            },
            "nics": {
                "eth0": {
                    "mac_addr": "de:ad:be:ef:20:14",
                    "port": "gi1/0/4",
                },
            },
        },

        {
            "uuid": Use(UUID),
            "free": True,
            "ipmi": {
                "host": "ipmi.node4.example.com",
                "user": "alice",
                "pass": "secret",
            },
            "nics": {
                "eth0": {
                    "uuid": Use(UUID),
                    "mac_addr": And(Use(str.lower), "de:ad:be:ef:20:14"),
                    "port": "gi1/0/4",
                },
            },
        }),

])
def test_uuid_object_create(typ, input, output):
    """Test ``api.uuid_object_create`` for various types & values."""
    result = api.uuid_object_create(typ, json.dumps(input))
    Schema(And(Use(json.loads, output))).validate(result)
