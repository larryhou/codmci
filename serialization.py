#!/usr/bin/env python3

import io

__author__ = 'larryhou'

def decode_system_information(text):
    string = io.StringIO(text)
    cursor = result = {}
    stack = [result]
    depth = {}
    indent = 0
    entity = None
    entity_name = ''
    for line in string.readlines():
        line = line[:-1].rstrip()
        if not line: continue
        padding = 0
        for n in range(len(line)):
            if line[n] != ' ':
                padding = n
                break
        sep = line.find(':')
        if indent != padding:
            if indent < padding:
                stack.append(cursor)
                depth[padding] = len(stack)
                if not isinstance(entity, dict):
                    entity = cursor[entity_name] = {}
                cursor = entity  # type: dict[str, any]
            else:
                shift = (len(stack) - depth[padding]) if padding in depth else len(stack) - 1
                while shift > 0:
                    cursor = stack.pop()
                    shift -= 1
            indent = padding
        entity_name = line[padding:sep].replace(' ', '')  # type: str
        entity = line[sep + 1:].lstrip()
        if not entity: entity = {}
        cursor[entity_name] = entity
    return result

def main():
    import sys, json
    result = decode_system_information(open(sys.argv[1], 'rb').read().decode('utf-8'))
    print(json.dumps(result, ensure_ascii=False, indent=4))

if __name__ == '__main__':
    main()
