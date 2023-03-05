class ParsedRequest:
    def __init__(self, request: str):
        self.raw = request.encode()
        lines = request.split('\r\n')
        self.request_line = lines[0]
        self.method, self.url, self.version = self.request_line.split(' ')

        self.headers = dict()
        for line in lines[1:len(lines)-2]:
            name, value = line.split(': ')
            self.headers[name] = value

    def maybe_lowercase(self, key: str):
        return key if key in self.headers else key.lower()

    def cache_hit_request(self, last_modified: str):
        request = ''
        request += self.request_line + '\r\n'
        for header, value in self.headers.items():
            request += f'{header}: {value}\r\n'
        request += f"If-Modified-Since: {last_modified}\r\n\r\n"
        return request.encode()


class ParsedResponse:
    def __init__(self, response: str):
        lines = response.split('\r\n')
        self.code = lines[0].split(' ')[1]

        self.headers = dict()
        for line in lines[1:len(lines)-2]:
            name, value = line.split(': ')
            self.headers[name] = value
