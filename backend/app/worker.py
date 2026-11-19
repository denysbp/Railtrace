from time import sleep

class Worker:
    def __init__(self):
        self.base = 1

    def run(self):
        while True:
            print(1)
            sleep(1)

if __name__ == "__main__":
    worker = Worker()
    worker.run()