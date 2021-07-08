
if __name__ == "__main__":
    # needed to prevent infinite process spawns when using pyintaller
    import multiprocessing
    multiprocessing.freeze_support()
    import sentry_sdk
    from subot.main import start_bot


    sentry_sdk.init(
        "https://90ff6a25ab444640becc5ab6a9e35d56@o914707.ingest.sentry.io/5855592",
        traces_sample_rate=1.0
    )
    start_bot()