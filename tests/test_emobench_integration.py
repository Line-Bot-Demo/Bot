from utils.emobench_adapter import predict

def test_predict_joy():
    assert predict("我今天很開心") == "joy"

def test_predict_sadness():
    assert predict("我今天很難過") == "sadness"

def test_predict_neutral():
    assert predict("這是一句普通的話") == "neutral"
