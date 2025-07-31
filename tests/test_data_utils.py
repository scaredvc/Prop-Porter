from scripts.init_data_load import convert_time_to_minutes

def test_convert_time_to_minutes():
    assert convert_time_to_minutes('0:00') == 0
    assert convert_time_to_minutes('1:00') == 1
    assert convert_time_to_minutes('1:30') == 1.5
    assert convert_time_to_minutes('2:00') == 2
    assert convert_time_to_minutes('2:30') == 2.5
    assert convert_time_to_minutes('3:00') == 3
    assert convert_time_to_minutes('3:30') == 3.5
    assert convert_time_to_minutes('4:00') == 4

def test_convert_time_to_minutes_edge_cases():
    assert convert_time_to_minutes('') == 0.0
    assert convert_time_to_minutes(None) == 0.0
    assert convert_time_to_minutes("invalid") == 0.0