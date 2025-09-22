# Filters to use with jinja2
import random


# Remove leading characters from the start of a string
def lstrip_chars(value, chars=' '):
    return value.lstrip(chars)

# Shuffles array
def shuffle(array):
    random.shuffle(array)
    return array 