from datetime import datetime


class Notification:
    def __init__(self, message: str):
        self.message = message
        self.timestamp = datetime.now()
        self.read = False

    def mark_as_read(self):
        self.read = True

    def __repr__(self):
        status = "lida" if self.read else "não lida"
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {self.message} ({status})"


class Post:
    _next_id = 1

    def __init__(self, author: str, content: str):
        self.id = Post._next_id
        Post._next_id += 1
        self.author = author
        self.content = content
        self.created_at = datetime.now()
        self.likes = 0
        self.dislikes = 0
        self.notifications = []

    def like(self):
        self.likes += 1

    def dislike(self):
        self.dislikes += 1

    def __repr__(self):
        return (
            f"Post(id={self.id}, author='{self.author}', content='{self.content}', "
            f"likes={self.likes}, dislikes={self.dislikes}, created_at={self.created_at:%Y-%m-%d %H:%M:%S})"
        )


class Feed:
    def __init__(self):
        self.posts = []

    def send_post(self, author: str, content: str) -> Post:
        post = Post(author, content)
        self.posts.append(post)
        return post

    def get_post(self, post_id: int) -> Post | None:
        return next((post for post in self.posts if post.id == post_id), None)

    def like_post(self, post_id: int, user: str) -> bool:
        post = self.get_post(post_id)
        if not post:
            return False
        post.like()
        post.notifications.append(Notification(f"{user} curtiu o post de {post.author}."))
        return True

    def dislike_post(self, post_id: int, user: str) -> bool:
        post = self.get_post(post_id)
        if not post:
            return False
        post.dislike()
        post.notifications.append(Notification(f"{user} não curtiu o post de {post.author}."))
        return True

    def post_notifications(self, post_id: int) -> list[Notification]:
        post = self.get_post(post_id)
        return post.notifications if post else []

    def feed_summary(self) -> str:
        if not self.posts:
            return "Feed vazio."
        lines = [f"Feed com {len(self.posts)} post(s):"]
        for post in self.posts:
            lines.append(
                f"{post.id}. {post.author}: {post.content} (👍 {post.likes} | 👎 {post.dislikes})"
            )
        return "\n".join(lines)


if __name__ == "__main__":
    feed = Feed()
    post1 = feed.send_post("Ana", "Compartilhando novidades sobre o projeto.")
    post2 = feed.send_post("Carlos", "Boa tarde, pessoal!")
    feed.like_post(post1.id, "Beatriz")
    feed.dislike_post(post2.id, "Daniel")
    print(feed.feed_summary())
    print("\nNotificações do post 1:")
    for notification in feed.post_notifications(post1.id):
        print(notification)
