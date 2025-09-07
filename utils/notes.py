
# Extracts parts of notes to display
def parse_notes(text):
    sections = []
    main_title = ""
    sub_title = ""
    content = []

    lines = text.strip().splitlines()
    for line in lines:
        if line.startswith("---"):
            continue

        if line.strip().startswith("### "):
            if len(content) > 0:
                sections.append({
                "main_title": main_title,
                "sub_title": sub_title,
                "content": content
                })
                content = [] 
            
            sub_title = line[4:]

        elif line.strip().startswith("## "):
            main_title = line[3:]
        
        elif line.strip().startswith("- "):
            content.append(line)
    
    sections.append({
        "main_title": main_title,
        "sub_title": sub_title,
        "content": content
    })
    print(sections)
    return sections