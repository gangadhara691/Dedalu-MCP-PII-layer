import json
from datasets import load_dataset



# Get only these entities we need
def has_place_name_entity(example):
    allowed_entities = ["人名", "法人名", "地名"]
    for entity in example["entities"]:
        if entity["type"] in allowed_entities:
            return True
    return False


# ex['entities'] is something like:
#      [{'name': '松友美佐紀', 'span': [0, 5], 'type': '人名'}
# We want to flatten it in a sense
def add_columns_from_entites(ex):
    
    def get_value(entity, entity_type):
        """Entity type is 地名, 人名 or 法人名"""
        all_found = [x["name"] for x in entity if x['type'] == entity_type]
        # return 1st found or empty string otherwise
        return "" if len(all_found) == 0 else all_found[0]
    
    return {
        "address": get_value(ex['entities'], "地名"),
        "full_name": get_value(ex['entities'], "人名"),
        "company_name": get_value(ex['entities'], "法人名"),
    }
    

# add a field called json with stringified json with needed labels
# this is what we want to predict
def add_json_label(ex):
    label_dict = {
        "full_name": ex.get('full_name', ''),
        "company_name": ex.get('company_name', ''),
        "address": ex.get('address', ''),
        "phone_number": ex.get('phone_number', '')
    }
    label_json = json.dumps(label_dict, ensure_ascii=False)
    return {"json": label_json}



def load_their_dataset():
    return (load_dataset("stockmark/ner-wikipedia-dataset")
        .filter(has_place_name_entity)
        .map(add_columns_from_entites)
        #.map(add_json_label)
    )