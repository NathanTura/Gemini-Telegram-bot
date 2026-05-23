from os import getenv

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=int(getenv("PORT", "8000")),
        reload=True,
    )
