from stage1.rules import serious_ae, prohibited_cm, protocol_version, lab_value

def test_hospitalization_is_serious():
    assert serious_ae({"AESER":"N","AESHOSP":"Y"})

def test_protocol_versions():
    assert protocol_version(4)==1
    assert protocol_version(8)==2
    assert protocol_version(9)==3

def test_sulfonylurea_only_v3():
    row={"CMCLAS":"SULFONYLUREA"}
    assert not prohibited_cm(row,2)
    assert prohibited_cm(row,3)

def test_s07_unit_conversion():
    value,qualifier,unit=lab_value({"LBTESTCD":"ALT","LBORRES":"3.995","LBORRESU":"ukat/L"})
    assert round(value,3)==239.7
    assert unit=="U/L"
