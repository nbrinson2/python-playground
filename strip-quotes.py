import json

def json_value_to_js(value):
    if isinstance(value, dict):
        return '{' + ', '.join(f"{k}: {json_value_to_js(v)}" for k, v in value.items()) + '}'
    elif isinstance(value, list):
        return '[' + ', '.join(json_value_to_js(v) for v in value) + ']'
    else:
        return json.dumps(value)

def json_to_js(input_filename, output_filename):
    with open(input_filename, 'r') as f:
        data = json.load(f)
    js_data = json_value_to_js(data)

    with open(output_filename, 'w') as f:
        f.write(js_data)

# test the function
json_to_js('input.json', 'output.js')
