class Worker:
    def __init__(self):
        self.base = 1

    def run(self):
        print(self.base)

if __name__ == "__main__":
    worker = Worker()
    worker.run()