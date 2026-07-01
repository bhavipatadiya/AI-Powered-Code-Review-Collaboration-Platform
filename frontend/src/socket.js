import { io } from "socket.io-client";

const socket = io(
  "https://ai-powered-code-review-collaboration-yzum.onrender.com"
);

export default socket;s