import os
class DocumentStore:
    def __init__(self,documents_dir):
        self.documents_dir=documents_dir
        self.docs={}
        if os.path.isdir(documents_dir):
            for name in os.listdir(documents_dir):
                if name.endswith(".md"):
                    with open(os.path.join(documents_dir,name),encoding="utf-8") as f:self.docs[name]=f.read()
    def get(self,name): return self.docs.get(name,"")
