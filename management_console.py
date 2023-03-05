from socket import *
import threading


class ManagementConsole:
    def __init__(self):
        self.new_request = None
        self.input_socket = socket()
        self.display_socket = socket()
        self.blocked_urls: set[str] = set()
        self.commands = dict()
        self.commands['block'] = self.block
        self.commands['unblock'] = self.unblock
        self.commands['list'] = self.list
        self.commands['exit'] = self.exit
        self.commands['help'] = self.help

    def start(self):
        self.input_socket.bind(('localhost', 5555))
        self.input_socket.listen(1)
        self.display_socket.bind(('localhost', 5556))
        self.display_socket.listen(1)
        print("Console is ready")

        while True:
            client_input, _ = self.input_socket.accept()
            threading.Thread(target=self.console_handler, args=(client_input,)).start()
            client_display, _ = self.display_socket.accept()
            threading.Thread(target=self.console_displayer, args=(client_display, )).start()

    def console_handler(self, client: socket):
        client.sendall('Type help for a list of available commands.\n '.encode())
        while True:
            client.sendall('> '.encode())
            command = client.recv(1024).decode('ASCII').strip()
            if command in self.commands:
                self.commands[command](client)
            else:
                client.sendall('Command unknown.\n'.encode())

    def console_displayer(self, client: socket):
        client.sendall('All requests going through the proxy server will be displayed here\n'.encode())
        while True:
            if self.new_request:
                client.sendall((self.new_request+'\n').encode())
                self.new_request = None

    def block(self, client: socket):
        client.sendall("Enter the URL to block: ".encode())
        url = client.recv(1024).decode('ASCII')
        self.blocked_urls.add(url.strip('\n '))
        client.sendall(f"URL successfully blocked: {url}\n".encode())

    def unblock(self, client: socket):
        client.sendall("Enter the URL to unblock: ".encode())
        url = client.recv(1024).decode('ASCII').strip('\n ')
        if url in self.blocked_urls:
            self.blocked_urls.remove(url)
            client.sendall(f"URL successfully unblocked: {url}\n".encode())
        else:
            client.sendall("The specified URL is not blocked\n".encode())

    def is_blocked(self, url: str):
        return url in self.blocked_urls

    def list(self, client: socket):
        client.sendall("List of blocked URLs: \n".encode())
        for url in self.blocked_urls:
            client.sendall((url+'\n').encode())

    def display_request(self, request: str):
        self.new_request = request

    @staticmethod
    def help(client: socket):
        client.sendall("Commands available: block | unblock | list | exit\n".encode())

    @staticmethod
    def exit(client: socket):
        client.close()


if __name__ == '__main__':
    console = ManagementConsole()
    console.start()
