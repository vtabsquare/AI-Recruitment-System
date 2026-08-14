import random
from datetime import datetime

def generate_application_id():

    year = datetime.now().year

    number = random.randint(1000, 9999)

    return f"VTAB-{year}-{number}"