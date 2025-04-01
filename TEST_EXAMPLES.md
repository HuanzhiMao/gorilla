# Single-Turn AST Evaluation (Both in Expert Curated and Crowd-Sourced)

## Simple
Simple function evaluation contains the simplest but most commonly seen format, where the user supplies a single JSON function document, with one and only one function call will be invoked.


### Test Entry
{"id": "simple_0", "question": [[{"role": "user", "content": "Find the area of a triangle with a base of 10 units and height of 5 units."}]], "function": [{"name": "calculate_triangle_area", "description": "Calculate the area of a triangle given its base and height.", "parameters": {"type": "dict", "properties": {"base": {"type": "integer", "description": "The base of the triangle."}, "height": {"type": "integer", "description": "The height of the triangle."}, "unit": {"type": "string", "description": "The unit of measure (defaults to 'units' if not specified)"}}, "required": ["base", "height"]}}]}

### Ground Truth Used for AST Evaluation
{"id": "simple_0", "ground_truth": [{"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}]}


## Multiple
Multiple function category contains a user question that only invokes one function call out of 2 to 4 JSON function documentations. The model needs to be capable of selecting the best function to invoke according to user-provided context.


### Test Entry
{"id": "multiple_0", "question": [[{"role": "user", "content": "Can I find the dimensions and properties of a triangle, if I know its three sides are 5 units, 4 units and 3 units long?"}]], "function": [{"name": "triangle_properties.get", "description": "Retrieve the dimensions, such as area and perimeter, of a triangle if lengths of three sides are given.", "parameters": {"type": "dict", "properties": {"side1": {"type": "integer", "description": "The length of first side of the triangle."}, "side2": {"type": "integer", "description": "The length of second side of the triangle."}, "side3": {"type": "integer", "description": "The length of third side of the triangle."}, "get_area": {"type": "boolean", "description": "A flag to determine whether to calculate the area of triangle. Default is true.", "default": true, "optional": true}, "get_perimeter": {"type": "boolean", "description": "A flag to determine whether to calculate the perimeter of triangle. Default is true.", "default": true, "optional": true}, "get_angles": {"type": "boolean", "description": "A flag to determine whether to calculate the internal angles of triangle. Default is true.", "default": true, "optional": true}}, "required": ["side1", "side2", "side3"]}}, {"name": "circle_properties.get", "description": "Retrieve the dimensions, such as area and circumference, of a circle if radius is given.", "parameters": {"type": "dict", "properties": {"radius": {"type": "float", "description": "The length of radius of the circle."}, "get_area": {"type": "boolean", "description": "A flag to determine whether to calculate the area of circle. Default is true.", "default": true, "optional": true}, "get_circumference": {"type": "boolean", "description": "A flag to determine whether to calculate the circumference of circle. Default is true.", "default": true, "optional": true}}, "required": ["radius"]}}]}

### Ground Truth Used for AST Evaluation
{"id": "multiple_0", "ground_truth": [{"triangle_properties.get": {"side1": [5], "side2": [4], "side3": [3], "get_area": ["", true], "get_perimeter": ["", true], "get_angles": ["", true]}}]}


## Parallel
Parallel function is defined as invoking multiple function calls in parallel with one user query. The model needs to digest how many function calls need to be made and the question to model can be a single sentence or multiple sentence.


### Test Entry
{"id": "parallel_0", "question": [[{"role": "user", "content": "Play songs from the artists Taylor Swift and Maroon 5, with a play time of 20 minutes and 15 minutes respectively, on Spotify."}]], "function": [{"name": "spotify.play", "description": "Play specific tracks from a given artist for a specific time duration.", "parameters": {"type": "dict", "properties": {"artist": {"type": "string", "description": "The artist whose songs you want to play."}, "duration": {"type": "integer", "description": "The duration for which the songs should be played, in minutes."}}, "required": ["artist", "duration"]}}]}

### Ground Truth Used for AST Evaluation
{"id": "parallel_0", "ground_truth": [{"spotify.play": {"artist": ["Taylor Swift"], "duration": [20]}}, {"spotify.play": {"artist": ["Maroon 5"], "duration": [15]}}]}


## Parallel Multiple
Parallel Multiple function is the combination of parallel function and multiple function. In other words, the model is provided with multiple function documentation, and each of the corresponding function calls will be invoked zero or more times.


### Test Entry
{"id": "parallel_multiple_0", "question": [[{"role": "user", "content": "Find the sum of all the multiples of 3 and 5 between 1 and 1000. Also find the product of the first five prime numbers."}]], "function": [{"name": "math_toolkit.sum_of_multiples", "description": "Find the sum of all multiples of specified numbers within a specified range.", "parameters": {"type": "dict", "properties": {"lower_limit": {"type": "integer", "description": "The start of the range (inclusive)."}, "upper_limit": {"type": "integer", "description": "The end of the range (inclusive)."}, "multiples": {"type": "array", "items": {"type": "integer"}, "description": "The numbers to find multiples of."}}, "required": ["lower_limit", "upper_limit", "multiples"]}}, {"name": "math_toolkit.product_of_primes", "description": "Find the product of the first n prime numbers.", "parameters": {"type": "dict", "properties": {"count": {"type": "integer", "description": "The number of prime numbers to multiply together."}}, "required": ["count"]}}]}

### Ground Truth Used for AST Evaluation
{"id": "parallel_multiple_0", "ground_truth": [{"math_toolkit.sum_of_multiples": {"lower_limit": [1], "upper_limit": [1000], "multiples": [[3, 5]]}}, {"math_toolkit.product_of_primes": {"count": [5]}}]}




## Relevance
In function relevance detection, we design scenarios where none of the provided functions are relevant and supposed to be invoked. We expect the model's output to be no function call. This scenario provides insight into whether a model will hallucinate on its function and parameter to generate function code despite lacking the function information or instructions from the users to do so.


### Test Entry
{"id": "live_relevance_0-0-0", "question": [[{"role": "user", "content": "I'd like to have a digital painting created. The image should be a detailed portrait of a masked woman, including bright peacock feathers, with an elegant and highly detailed style. It should have a fluid illustration quality, with green highlighted lines and complex patterns, reminiscent of cyberpunk and Alphonse Mucha's art."}]], "function": [{"name": "search_engine.query", "description": "Conducts a search based on the provided prompt and returns relevant real-time information, specific details, or general facts from various sources, including internet browsing and data from Google.", "parameters": {"type": "dict", "required": ["prompt"], "properties": {"prompt": {"type": "string", "description": "The search query to be executed by the search engine. Example: 'latest scientific discoveries'."}, "since_year": {"type": "integer", "description": "Filter results to include only information published after the specified year. Default to the current year if not provided.", "default": 2023}, "source": {"type": "string", "description": "Preferred source for the search results, such as 'all', 'internet', or 'google'.", "enum": ["all", "internet", "google"], "default": "all"}, "include_facts": {"type": "boolean", "description": "Indicates whether to include factual information in the search results. Default is true.", "default": true}}}}, {"name": "generate_image", "description": "Generate an image based on a given text prompt. The function is versatile and can be used for various general purposes without specializing in any specific category.", "parameters": {"type": "dict", "required": ["prompt"], "properties": {"prompt": {"type": "string", "description": "The text prompt that describes the desired content of the image."}, "image_format": {"type": "string", "description": "The file format for the output image.", "enum": ["JPEG", "PNG", "BMP"], "default": "PNG"}, "width": {"type": "integer", "description": "The width of the generated image in pixels.", "default": 1024}, "height": {"type": "integer", "description": "The height of the generated image in pixels.", "default": 768}, "color_mode": {"type": "string", "description": "The color mode of the image.", "enum": ["RGB", "Grayscale"], "default": "RGB"}}}}, {"name": "generate_human_image", "description": "Generates a realistic image of a human based on the provided prompt, with options for creating images representing different age groups and genders.", "parameters": {"type": "dict", "required": ["prompt", "image_quality"], "properties": {"prompt": {"type": "string", "description": "A descriptive text guiding the generation of the human image, such as 'a smiling girl with blue eyes' or 'an elderly man playing chess'."}, "image_quality": {"type": "string", "description": "The desired quality of the generated image, affecting the level of detail and realism. Options include 'low', 'medium', and 'high'.", "enum": ["low", "medium", "high"]}, "include_background": {"type": "boolean", "description": "Determines whether a background should be included in the generated image.", "default": false}, "output_format": {"type": "string", "description": "Specifies the file format for the output image.", "enum": ["JPEG", "PNG", "BMP"], "default": "JPEG"}}}}]}

### Ground Truth Used for AST Evaluation
***Any Valid Function Call***


## Irrelevance
In function irrelevance detection, we design scenarios where none of the provided functions are relevant and supposed to be invoked. We expect the model's output to be no function call. This scenario provides insight into whether a model will hallucinate on its function and parameter to generate function code despite lacking the function information or instructions from the users to do so.
### Test Entry
{"id": "live_irrelevance_0-0-0", "question": [[{"role": "user", "content": "Can you provide the address for latitude 37.4224764 and longitude -122.0842499 using the Geocoding API?"}]], "function": [{"name": "requests.get", "description": "Sends a GET request to the specified URL to retrieve data. This function is commonly used for API calls and web scraping.", "parameters": {"type": "dict", "required": ["url"], "properties": {"url": {"type": "string", "description": "The URL to which the GET request is sent using the Date Nager API to access holiday information for over 100 countries. The API uses ISO 3166-1 alpha-2 country codes. More information can be found at https://date.nager.at/Api"}, "headers": {"type": "dict", "properties": {"Content-Type": {"type": "string", "description": "The media type of the resource being requested, typically 'application/json'.", "default": "application/json"}, "Authorization": {"type": "string", "description": "The credentials to authenticate a user agent with a server, typically formatted as 'Bearer {token}'."}}, "description": "Headers to include in the request.", "default": {}}, "timeout": {"type": "float", "description": "The maximum amount of time to wait for a response from the server, in seconds. A longer timeout may be necessary for slower network connections or overloaded servers.", "default": 5.0}, "params": {"type": "dict", "description": "Query parameters for the request, allowing for complex searches and filtering.", "properties": {"query": {"type": "string", "description": "The query parameter for search or filtering."}, "page": {"type": "integer", "description": "The page number parameter for pagination. Used to retrieve a specific page of results.", "default": 1}}, "default": {}}, "auth": {"type": "array", "items": {"type": "string"}, "description": "HTTP authentication credentials formatted as a (username, password) tuple.", "default": []}, "cert": {"type": "string", "description": "Path to the SSL client certificate file (.pem), if required for the request."}, "cookies": {"type": "dict", "properties": {"sessionid": {"type": "string", "description": "Session identifier cookie, used to recognize client sessions on the server."}, "csrftoken": {"type": "string", "description": "CSRF protection token cookie, used to prevent cross-site request forgery attacks."}}, "description": "Cookies to include in the request."}, "proxies": {"type": "dict", "properties": {"http": {"type": "string", "description": "Proxy URL to use for HTTP requests, including the port number."}, "https": {"type": "string", "description": "Proxy URL to use for HTTPS requests, including the port number."}}, "description": "Proxy configuration for the request."}, "stream": {"type": "boolean", "description": "Whether to stream the download of the response. If False, the response content will be immediately downloaded. Streaming is useful for handling large files or responses.", "default": false}, "verify": {"type": "boolean", "description": "Whether to verify the server's TLS certificate or not. Set to False to skip certificate verification, which is not recommended unless you are sure of the server's identity.", "default": true}}}}]}


### Ground Truth Used for AST Evaluation
***No Function Call***

# Single-Turn Executable Evaluation (in Expert Curated)
> In the executable test category, we execute the generated API call to check for response correctness.
> Evaluation criteria (either of the following must be met, depending on the executable function example):
> - Exact match: The output must exactly match the expected result.
> - Real-time match: A looser form of exact match that only applies to numerical execution result, where the execution result must be within a certain percentage threshold (20%) from the expected result to accommodate the live updates of API responses.
> - Structural match: The output must match the expected data type. For example, both [1, 2, 3] and [1.5, 2.4, 6] are accepted if the expected type is a list. In addition, the following types have some special requirements:

## Simple
### Test Entry
{"id": "exec_simple_0", "question": [[{"role": "user", "content": "I've been playing a game where rolling a six is somehow more likely than usual, and the chance of it happening on a single roll is 60%. I'm curious, if I roll the die 20 times, what are the odds that I'll get exactly five sixes?"}]], "function": [{"name": "calc_binomial_probability", "description": "Calculates the probability of getting k successes in n trials.", "parameters": {"type": "dict", "properties": {"n": {"type": "integer", "description": "The number of trials."}, "k": {"type": "integer", "description": "The number of successes."}, "p": {"type": "float", "description": "The probability of success."}}, "required": ["n", "k", "p"]}}]}

### Ground Truth Used for Executable Evaluation
{"id":"exec_simple_0","ground_truth":["calc_binomial_probability(n=20, k=5, p=0.6)"],"execution_result_type":["exact_match"]}

## Multiple

### Test Entry
{"id": "exec_multiple_0", "question": [[{"role": "user", "content": "I'm playing a dice game and want to calculate my chances. I roll the die 20 times, and I'm trying to figure out the probability of landing on a 6 exactly five times, considering each roll has a one in six chance of being a 6. Could you help me with that?"}]], "function": [{"name": "get_weather_data", "description": "Fetches weather data from the Open-Meteo API for the given latitude and longitude.", "parameters": {"type": "dict", "properties": {"coordinates": {"type": "array", "items": {"type": "float"}, "description": "The latitude and longitude of the location."}}, "required": ["coordinates"]}}, {"name": "calc_binomial_probability", "description": "Calculates the probability of getting k successes in n trials.", "parameters": {"type": "dict", "properties": {"n": {"type": "integer", "description": "The number of trials."}, "k": {"type": "integer", "description": "The number of successes."}, "p": {"type": "float", "description": "The probability of success."}}, "required": ["n", "k", "p"]}}]}

### Ground Truth Used for Executable Evaluation
{"id":"exec_multiple_0","ground_truth":["calc_binomial_probability(n=20, k=5, p=1/6)"],"execution_result_type":["exact_match"]}

## Parallel
### Test Entry
{"id": "exec_parallel_0", "question": [[{"role": "user", "content": "I'm trying to understand my chances in a game with a 30% win probability per round. Can you calculate the probability of winning exactly 3 out of 10 rounds, 5 out of 15 rounds, and 7 out of 20 rounds?"}]], "function": [{"name": "calc_binomial_probability", "description": "Calculates the probability of getting k successes in n trials.", "parameters": {"type": "dict", "properties": {"n": {"type": "integer", "description": "The number of trials."}, "k": {"type": "integer", "description": "The number of successes."}, "p": {"type": "float", "description": "The probability of success."}}, "required": ["n", "k", "p"]}}]}

### Ground Truth Used for Executable Evaluation
{"id":"exec_parallel_0","ground_truth":["calc_binomial_probability(n=10, k=3, p=0.3)","calc_binomial_probability(n=15, k=5, p=0.3)","calc_binomial_probability(n=20, k=7, p=0.3)"],"execution_result_type":["exact_match","exact_match","exact_match"]}

## Parallel Multiple
### Test Entry
{"id": "exec_parallel_multiple_0", "question": [[{"role": "user", "content": "I'm planning a small outdoor event in Ottawa, and I need to make sure the weather is going to cooperate. Could you fetch the current weather for me at latitude 45.4215 and longitude -75.6972 using the Open-Meteo API? Also, I'm running a small game at the event, and I'm curious about the chances of winning. If I have 10 attempts at this game and the chance of winning each time is 50%, how likely is it that I'll win 5 times?"}]], "function": [{"name": "get_weather_data", "description": "Fetches weather data from the Open-Meteo API for the given latitude and longitude.", "parameters": {"type": "dict", "properties": {"coordinates": {"type": "array", "items": {"type": "float"}, "description": "The latitude and longitude of the location."}}, "required": ["coordinates"]}}, {"name": "calc_binomial_probability", "description": "Calculates the probability of getting k successes in n trials.", "parameters": {"type": "dict", "properties": {"n": {"type": "integer", "description": "The number of trials."}, "k": {"type": "float", "description": "The number of successes."}, "p": {"type": "float", "description": "The probability of success."}}, "required": ["n", "k", "p"]}}]}

### Ground Truth Used for Executable Evaluation
{"id":"exec_parallel_multiple_0","ground_truth":["get_weather_data(coordinates=[45.4215, -75.6972])","calc_binomial_probability(n=10, k=5, p=0.5)"],"execution_result_type":["structural_match","exact_match"]}

# Multi-Turn (Base, Miss_Func, Miss_Params, Long Ctx)

## API Domains and Tools (8 APIs in total)
### FileSystem API
Examples
- cat
- cd
- cp
### Math API
Examples
- absolute_value
- add
- divide

### Twitter API
Examples
- authenticate_twitter
- comment
- follow_user

### Ticket API
Examples
- close_ticket
- create_ticket
- edit_ticket


### Trading Bot API
Examples
- add_to_watchlist
- cancel_order
- filter_stocks_by_price


### Travel Booking API
Examples
- authenticate_travel
- book_flight
- cancel_booking



### Vehicle Control API
Examples
- activateParkingBrake
- adjustClimateControl
- check_tire_pressure


## Multi-Turn Base

### Test Entry
{"id": "multi_turn_base_50", "question": [[{"role": "user", "content": "Hey there, I noticed that all of my car doors seem to have locked themselves up, and with my schedule being pretty tight today, I'm in quite a pinch. I could really use your help to get those doors unlocked. It'd be fantastic if you could also switch on the headlights. It's getting a bit darker out here than expected, and visibility's not great!"}]], "initial_config": {"VehicleControlAPI": {"fuelLevel": 10.5, "batteryVoltage": 12.6, "engineState": "stopped", "doorStatus": {"driver": "locked", "passenger": "locked", "rear_left": "locked", "rear_right": "locked"}, "acTemperature": 22.0, "fanSpeed": 70, "acMode": "auto", "humidityLevel": 45.0, "headLightStatus": "off", "parkingBrakeStatus": "released", "parkingBrakeForce": 0.0, "slopeAngle": 0.0, "distanceToNextVehicle": 30.0, "cruiseStatus": "inactive", "destination": "None", "frontLeftTirePressure": 32.0, "frontRightTirePressure": 32.0, "rearLeftTirePressure": 30.0, "rearRightTirePressure": 30.0}}, "path": ["VehicleControlAPI.displayCarStatus", "VehicleControlAPI.lockDoors", "VehicleControlAPI.setHeadlights"], "involved_classes": ["VehicleControlAPI"]}


### Ground Truth Used for Stateful and Response Evaluation
{"id": "multi_turn_base_50", "ground_truth": [["lockDoors(unlock=True, door=['driver', 'passenger', 'rear_left', 'rear_right'])", "setHeadlights(mode='on')"]]}


## Multi-Turn Miss_Func


### Test Entry
{"id": "multi_turn_miss_func_50", "question": [[{"role": "user", "content": "Hey there, I noticed that all of my car doors seem to have locked themselves up, and with my schedule being pretty tight today, I'm in quite a pinch. I could really use your help to get those doors unlocked. It'd be fantastic if you could also switch on the headlights. It's getting a bit darker out here than expected, and visibility's not great!"}], []], "initial_config": {"VehicleControlAPI": {"fuelLevel": 10.5, "batteryVoltage": 12.6, "engineState": "stopped", "doorStatus": {"driver": "locked", "passenger": "locked", "rear_left": "locked", "rear_right": "locked"}, "acTemperature": 22.0, "fanSpeed": 70, "acMode": "auto", "humidityLevel": 45.0, "headLightStatus": "off", "parkingBrakeStatus": "released", "parkingBrakeForce": 0.0, "slopeAngle": 0.0, "distanceToNextVehicle": 30.0, "cruiseStatus": "inactive", "destination": "None", "frontLeftTirePressure": 32.0, "frontRightTirePressure": 32.0, "rearLeftTirePressure": 30.0, "rearRightTirePressure": 30.0}}, "path": ["VehicleControlAPI.displayCarStatus", "VehicleControlAPI.lockDoors", "VehicleControlAPI.setHeadlights"], "involved_classes": ["VehicleControlAPI"], "missed_function": {"1": ["lockDoors"]}}

### Ground Truth Used for Stateful and Response Evaluation
{"id": "multi_turn_miss_func_50", "ground_truth": [[], ["lockDoors(unlock=True, door=['driver', 'passenger', 'rear_left', 'rear_right'])", "setHeadlights(mode='on')"]]}


## Multi-Turn Miss_Params
### Test Entry
{"id": "multi_turn_miss_param_50", "question": [[{"role": "user", "content": "Hey there, I noticed that all of my car doors seem to have locked themselves up, and with my schedule being pretty tight today, I'm in quite a pinch. I could really use your help to get some of them unlocked."}], [{"role": "user", "content": "I mean could you help me get all those doors unlocked? It'd be fantastic if you could also switch on the headlights. It's getting a bit darker out here than expected, and visibility's not great!"}]], "initial_config": {"VehicleControlAPI": {"fuelLevel": 10.5, "batteryVoltage": 12.6, "engineState": "stopped", "doorStatus": {"driver": "locked", "passenger": "locked", "rear_left": "locked", "rear_right": "locked"}, "acTemperature": 22.0, "fanSpeed": 70, "acMode": "auto", "humidityLevel": 45.0, "headLightStatus": "off", "parkingBrakeStatus": "released", "parkingBrakeForce": 0.0, "slopeAngle": 0.0, "distanceToNextVehicle": 30.0, "cruiseStatus": "inactive", "destination": "None", "frontLeftTirePressure": 32.0, "frontRightTirePressure": 32.0, "rearLeftTirePressure": 30.0, "rearRightTirePressure": 30.0}}, "path": ["VehicleControlAPI.displayCarStatus", "VehicleControlAPI.lockDoors", "VehicleControlAPI.setHeadlights"], "involved_classes": ["VehicleControlAPI"]}

### Ground Truth Used for Stateful and Response Evaluation
{"id": "multi_turn_miss_param_50", "ground_truth": [[], ["lockDoors(unlock=True, door=['driver', 'passenger', 'rear_left', 'rear_right'])", "setHeadlights(mode='on')"]]}


## Multi-Turn Long Ctx

### Test Entry
{"id": "multi_turn_long_context_50", "question": [[{"role": "user", "content": "Hey there, I noticed that all of my car doors seem to have locked themselves up, and with my schedule being pretty tight today, I'm in quite a pinch. I could really use your help to get those doors unlocked. It'd be fantastic if you could also switch on the headlights. It's getting a bit darker out here than expected, and visibility's not great!"}]], "initial_config": {"VehicleControlAPI": {"fuelLevel": 10.5, "batteryVoltage": 12.6, "engineState": "stopped", "doorStatus": {"driver": "locked", "passenger": "locked", "rear_left": "locked", "rear_right": "locked"}, "acTemperature": 22.0, "fanSpeed": 70, "acMode": "auto", "humidityLevel": 45.0, "headLightStatus": "off", "parkingBrakeStatus": "released", "parkingBrakeForce": 0.0, "slopeAngle": 0.0, "distanceToNextVehicle": 30.0, "cruiseStatus": "inactive", "destination": "None", "frontLeftTirePressure": 32.0, "frontRightTirePressure": 32.0, "rearLeftTirePressure": 30.0, "rearRightTirePressure": 30.0}}, "path": ["VehicleControlAPI.displayCarStatus", "VehicleControlAPI.lockDoors", "VehicleControlAPI.setHeadlights"], "involved_classes": ["VehicleControlAPI"]}

### Ground Truth Used for Stateful and Response-based Evaluation
{"id": "multi_turn_long_context_50", "ground_truth": [["lockDoors(unlock=True, door=['driver', 'passenger', 'rear_left', 'rear_right'])", "setHeadlights(mode='on')"]]}


# Memory

## Tools
- long_term_memory_add
- long_term_memory_clear
- long_term_memory_key_search
- long_term_memory_list_keys
- long_term_memory_remove
- long_term_memory_replace
- long_term_memory_retrieve
- short_term_memory_add
- short_term_memory_clear
- short_term_memory_key_search
- short_term_memory_list_keys
- short_term_memory_remove
- short_term_memory_replace
- short_term_memory_retrieve
- short_term_memory_retrieve_all

## Memory Healthcare (example categories)

### Prereq Conversation (used for model memory store)
Topic 1: General History
Multi-turn Conversation
Turn 1: Oh, hey! Yeah, I’ve had my fair share of health ups and downs over the years. Being in my mid-50s now, I feel like I’ve seen it all—surgeries, medications, chronic
Turn 2: Let me break it down for you. The biggest health issue I deal with is Type 2 Diabetes. I was diagnosed about ten years ago, and at first, it was a real struggle.
Turn 3: Aside from that, I have hypertension, which runs in my family. It’s something I’ve been managing for a while now with medication and lifestyle changes. Stress can really make it worse, and I’ve noticed that over the years. I try to keep my blood pressure in check by eating right and doing some light exercise—mostly walking and yoga. 
...
Turn 10: Overall, though, I’m doing my best to stay healthy. I used to worry a lot about getting older and what that would mean for my health, but now I just focus on taking it one step at a time.

Topic 2: Health and Lifestyle

Topic 3: Aging

Topic 4: Test Results

Topic 5: Medication and Treatments

### Test Entry (used for model memory retrieval)
{"id": "memory_base_0", "question": [[{"role": "patient", "content": "What is the biggest health issue mentioned by the patient?"}]], "involved_classes": ["MemoryAPI"]}

### Ground Truth Used for Response-based Evaluation
{"id":"memory_base_0","ground_truth":["Type 2 Diabetes","Diabetes"],"source":"\"The biggest health issue I deal with is Type 2 Diabetes.\""}

# Web Search

## Tools
- duckduckgo_search
- fetch_url_content

## Web Search Base
### Test Entry
{"id": "web_search_0", "question": [[{"role": "user", "content": "Some countries are known for producing luxury goods, including the world's most expensive tea. In 2024, who is the richest billionaire (according to Forbes) from the country that produces the most expensive tea?"}]], "involved_classes": ["WebSearchAPI"]}

### Ground Truth Use for Response-based Evaluation
{"id": "web_search_0", "ground_truth": ["Zhong Shanshan"], "source": [{"subquestion": "Most expensive tea in the world", "answer": "DaHong Pao", "source": "https://camellios.com/blogs/the-camellios-blog/the-5-most-expensive-teas-in-the-world#:~:text=Da%20Hong%20Pao%2C%20the%20legendary,back%20to%20the%20Ming%20Dynasty."}, {"subquestion": "Country that produces DaHong Pao", "answer": "China", "source": "https://en.wikipedia.org/wiki/Da_Hong_Pao#:~:text=Da%20Hong%20Pao%20(Big%20Red,Mountains%20of%20Fujian%20Province%2C%20China."}, {"subquestion": "Who is the richest billionaire in China", "answer": "Zhong Shanshan", "source": "https://www.forbes.com/lists/china-billionaires/"}], "num_hops": 3}

