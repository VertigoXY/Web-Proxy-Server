import threading
import time
from socket import *
from http_parser import ParsedRequest, ParsedResponse
from management_console import ManagementConsole
from collections import OrderedDict


class ProxyServer:
    CONNECTION_ESTABLISHED = 'HTTP/1.1 200 Connection Established\r\n\r\n'.encode()
    NOT_IMPLEMENTED = 'HTTP/1.1 501 Not Implemented\r\n\r\n'.encode()
    FORBIDDEN = 'HTTP/1.1 403 Forbidden\r\n\r\n'.encode()
    BUFFER_SIZE = 1024

    def __init__(self, hostname, port, *, console):
        self.hostname = hostname
        self.port = port
        self.cache = OrderedDict()
        self.console: ManagementConsole = console
        self.socket = socket()

    def start(self):
        self.socket.bind((self.hostname, self.port))
        self.socket.listen(5)
        print(f"Proxy server is listening on {self.hostname}:{self.port}")
        threading.Thread(target=self.console.start).start()

        while True:
            client_socket, client_addr = self.socket.accept()
            threading.Thread(target=self.client_handler, args=(client_socket,)).start()

    def client_handler(self, client: socket):
        cache_hit = False
        client_request = client.recv(1024)
        parsed_request = ParsedRequest(client_request.decode('ASCII'))

        if self.console.is_blocked(parsed_request.url):
            self.console.display_request(parsed_request.request_line + " (BLOCKED)")
            client.sendall(self.FORBIDDEN)
            client.shutdown(SHUT_RDWR)
            client.close()
            return

        if parsed_request.url in self.cache:
            cache_hit = True
            parsed_request.raw = parsed_request.cache_hit_request(self.cache[parsed_request.url]['last-modified'])

        if parsed_request.method == 'GET':
            host = parsed_request.headers[parsed_request.maybe_lowercase('Host')]
            self.http_handler(client, parsed_request, host, cache_hit, parsed_request.url)
        elif parsed_request.method == 'CONNECT':
            self.console.display_request(parsed_request.request_line)
            host, port = parsed_request.headers[parsed_request.maybe_lowercase('Host')].split(':')
            self.https_websockets_handler(client, host, int(port))
        else:
            client.sendall(self.NOT_IMPLEMENTED)
            client.shutdown(SHUT_RDWR)
            client.close()

    def http_handler(self, client: socket, parsed_request: ParsedRequest, host: str, cache_hit: bool, url: str):
        server = create_connection((host, 80))
        start = time.time()
        server.sendall(parsed_request.raw)
        server.shutdown(SHUT_WR)
        response = b''
        while data := server.recv(self.BUFFER_SIZE):
            response += data

        parsed_response = ParsedResponse(response.decode('latin-1'))

        if cache_hit:
            if int(parsed_response.code) == 304:
                self.console.display_request(parsed_request.request_line + ' (Cache Hit - 3O4 Not Modified)')
                client.sendall(self.cache[url]['response'])
            else:
                self.console.display_request(parsed_request.request_line + ' (Cache Hit - Resource Modified)')
                self.cache[url] = {'last-modified': parsed_response.headers['Last-Modified'], 'response': response}
                client.sendall(response)

        else:
            if 'Last-Modified' in parsed_response.headers:
                self.console.display_request(parsed_request.request_line + ' (Cache Miss - Resource cached)')
                if len(self.cache) == 256:
                    self.cache.popitem(last=False)
                self.cache[url] = {'last-modified': parsed_response.headers['Last-Modified'], 'response': response}
            else:
                self.console.display_request(parsed_request.request_line + ' (Cache Miss - Resource not cacheable)')
            client.sendall(response)

        end = time.time()
        with open('data.out', 'a') as file:
            file.write(f'{parsed_request.url} -- Cache Hit: {cache_hit} -- {end-start} sec\n')
        server.close()
        client.shutdown(SHUT_RDWR)
        client.close()

    # A CONNECT HTTP request means that the client just wants the proxy to forward the TCP connection to the end server.
    # The proxy just makes the connection on behalf of the client, and then proxies the stream to and from the client.
    # The proxy doesn't read or process any data; it just streams it, so any encrypted data can transit, as well as
    # data for protocols that the proxy itself may not understand. In this case, HTTP over TLS requests (with encrypted
    # data) and Websockets connections can be made by just creating a TCP tunnel.
    def https_websockets_handler(self, client: socket, host: str, port: int):
        server = socket()
        server.connect((host, port))
        client.sendall(self.CONNECTION_ESTABLISHED)

        self.tunnel(client, server)

    def tunnel(self, client: socket, server: socket):
        threading.Thread(target=self.proxy_data, args=(server, client)).start()
        self.proxy_data(client, server)

    def proxy_data(self, source: socket, destination: socket):
        while data := source.recv(self.BUFFER_SIZE):
            destination.sendall(data)


if __name__ == '__main__':
    management_console = ManagementConsole()
    proxy = ProxyServer('localhost', 8080, console=management_console)
    proxy.start()

