
import pytest
from haas.model import *

@pytest.mark.parametrize('cls,input', [
    (Node, {}),
    (Node, {
        "ipmi": {
            "user": "alice",
            "host": "wonderland",
            "password": "jabberwocky",  # The correct field name is "pass".
         },
    }),

    (Nic, {}),
    (Nic, {
        "mac_addr": "de:ad:be:ef:20:14",
    }),
    (Nic, {
        "mac": "de:ad:be:ef:20:14",
        "port": "gi1/0/4",
    }),
])
def test_from_json_bad_input(cls, input):
    """If a client tries to create an object via illegal JSON, it should fail.

    In particular, it should raise a MalformedInputError.
    """
    with pytest.raises(MalformedInputError):
        cls.from_json(input)
