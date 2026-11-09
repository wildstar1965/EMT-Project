import copy
import json
from pathlib import Path
from unittest.mock import patch
from airdesk.common import load_config, config_hash
from airdesk.evidence import VerifiedPower


def test_success_flag_without_artifacts_cannot_enable_charging():
    cfg=load_config()
    fake={"config_sha256":config_hash(cfg),"executed":True,"passed":True,"artifacts":[]}
    with patch.object(Path,"read_text",return_value=json.dumps(fake)):
        power=VerifiedPower(cfg,Path("unused-test-double.json"))
    assert not power.available and power.watts==0


def test_stale_configuration_is_rejected_before_loading_artifacts():
    cfg=load_config()
    previous={"config_sha256":config_hash(cfg),"executed":True,"passed":True}
    changed=copy.deepcopy(cfg)
    changed["table"]["thickness_mm"]+=1
    with patch.object(Path,"read_text",return_value=json.dumps(previous)):
        power=VerifiedPower(changed,Path("unused-test-double.json"))
    assert not power.available and "stale" in power.reason.lower()
