
import marqo

mq = marqo.Client(url='http://localhost:8882')
mq.create_index("my-first-index", model="hf/e5-base-v2")


