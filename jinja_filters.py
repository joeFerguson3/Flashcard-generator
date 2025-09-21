# Filters to use with jinja2

# Remove leading characters from the start of a string
def lstrip_chars(value, chars=' '):
    return value.lstrip(chars)