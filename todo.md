SNS 구현
사용할 기술,
EMAIL
CACHE
S3
WebSocket
AI?

1. POST기능
2. Follow기능
3. Favorite기능
4. Bookmark기능
5. Repost기능
    1. 팔로우한 사람이 Repost한 글들을 최신순으로, 팔로우한 사람이 작성한 글을 최신순으로
6. Notification기능
    4. mention
    1. favorite
    2. repost
    6. replied
    3. quote
    5. follow
    6. 자신에게의 알림은 생성하지 않는게 좋음 지금은 생성된 후  signals에서 체크하여 인스턴스를 삭제함. 추후 개선필요
7. Chat 기능