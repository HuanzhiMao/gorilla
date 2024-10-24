import re
import json
import inspect
from typing import Dict, Union, Optional, get_origin, get_args

#Type Conversions
def convert_type_to_json_compatible(type_name: str) -> str:
    type_mapping = {
        "str": "string",
        "int": "integer",
    }
    return type_mapping.get(type_name, type_name)

def parse_docstring(docstring: str) -> Dict[str, Union[str, dict]]:
    # Set up description, parameters, and response
    description = ""
    parameters = {}
    required_params = []
    response = {"properties": {}}
    response_description = ""

    lines = docstring.strip().split('\n')
    current_section = None

    for line in lines:
        line = line.strip()
        if line.startswith("Args:"):
            current_section = "parameters"
            continue
        elif line.startswith("Returns:"):
            current_section = "response"
            continue
        
        # Takes the description as it comes before 'Args:' or 'Returns:'
        if current_section is None:
            description += line + " "
        # Now processes the parameters
        elif current_section == "parameters":
            match = re.match(r"(\w+) \(([\w\[\]]+)\): (.+)", line)
            if match:
                param_name, param_type, param_desc = match.groups()
                # Handles if optional types
                is_optional = False
                if param_type.startswith("Optional["):
                    param_type = param_type[len("Optional["):-1]
                    is_optional = True

                param_type = convert_type_to_json_compatible(param_type)

                param_desc = param_desc.replace("Optional ", "").strip()

                # Checks for required parameters
                if "[Required]" in param_desc:
                    required_params.append(param_name)
                    param_desc = param_desc.replace("[Required]", "").strip()
                
                param_entry = {
                    "type": param_type,
                    "description": param_desc
                }

                if is_optional:
                    param_entry["default_value"] = None

                parameters[param_name] = param_entry
        # Handles response
        elif current_section == "response":
            # Match a single return value
            single_match = re.match(r"(\w+) \(([\w\[\]]+)\): (.+)", line)
            
            if single_match:
                response_name, response_type, response_desc = single_match.groups()

                response_type = convert_type_to_json_compatible(response_type)

                response_description = response_desc.strip()
                
                response["properties"][response_name] = {
                    "type": response_type,
                    "description": response_desc.strip()
                }

    parameters_structure = {
        "type": "dict",
        "properties": parameters
    }

    if required_params:
        parameters_structure["required"] = required_params

    return {
        "description": description.strip(),
        "parameters": parameters_structure,
        "response_properties": response.get("properties", {}),
        "response_description": response_description
    }

def determine_response_structure(func) -> dict:
    # Uses inspect to get the signature and return type of the function
    sig = inspect.signature(func)
    return_type = sig.return_annotation

    # if return type is dictionary-like structure
    if get_origin(return_type) == dict:
        response_structure = {
            "type": "dict",
            "properties": {}
        }

        type_args = get_args(return_type)
        if type_args and type_args[0] == str:
            return response_structure
    
    # if return type is simple (str, int, float)
    if return_type in [str, int, float]:
        return {
            "type": convert_type_to_json_compatible(return_type.__name__),
            "description": ""
        }

    return {
        "type": "dict",
        "properties": {}
    }

def function_to_json(func) -> str:
    func_name = func.__name__
    docstring = func.__doc__
    
    if not docstring:
        raise ValueError("Function must have a docstring.")
    
    parsed_data = parse_docstring(docstring)
    
    response_structure = determine_response_structure(func)
    
    if response_structure["type"] == "dict" and parsed_data["response_properties"]:
        response_structure["properties"] = parsed_data["response_properties"]

    if response_structure["type"] != "dict" and parsed_data["response_description"]:
        response_structure["description"] = parsed_data["response_description"]

    json_representation = {
        "name": func_name,
        "description": parsed_data["description"],
        "parameters": parsed_data["parameters"],
        "response": response_structure
    }
    
    sig = inspect.signature(func)
    for param_name, param in sig.parameters.items():
        if param.default is not inspect.Parameter.empty:
            if param_name in json_representation["parameters"]["properties"]:
                json_representation["parameters"]["properties"][param_name]["default_value"] = param.default

    return json.dumps(json_representation, indent=4)

# PROOF OF CONCEPT TEST
class TestAPI:
    #Amitoj Note: PASTE WHICHEVER FUNCTION YOU WANT TO CHECK HERE AND REPLACE
    def authenticate_travel(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        grant_type: str,
        user_first_name: str,
        user_last_name: str,
    ) -> Dict[str, Union[int, str]]:
        """
        Authenticate the user with the travel API

        Args:
            client_id (str): [Required] The client applications client_id supplied by App Management
            client_secret (str): [Required] The client applications client_secret supplied by App Management
            refresh_token (str): [Required] The refresh token obtained from the initial authentication
            grant_type (str): [Required] The grant type of the authentication request. Here are the options: read_write, read, write
            user_first_name (str): [Required] The first name of the user
            user_last_name (str): [Required] The last name of the user
        Returns:
            expires_in (int): The number of time it can use until the access token expires
            access_token (str): The access token to be used in the Authorization header of future requests
            token_type (str): The type of token
            scope (str): The scope of the token
        """
        self.token_expires_in = 2
        self.access_token = str(self._random.randint(100000, 999999))  # 6 digits
        self.token_type = "Bearer"
        self.token_scope = grant_type
        self.user_first_name = user_first_name
        self.user_last_name = user_last_name
        return {
            "expires_in": 2,
            "access_token": self.access_token,
            "token_type": "Bearer",
            "scope": grant_type,
        }

# Convert example function to JSON
test_api = TestAPI()
#Amitoj Note: REPLACE WITH FUNCTION NAME BEING TESTED FROM ABOVE
print(function_to_json(test_api.authenticate_travel))

#TO RUN DO: python api_to_json.py