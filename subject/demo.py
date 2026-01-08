from subject.core import Subject


def main() -> None:
    s = Subject(initial_value=0, initial_budget=1)

    print("STEP 1")
    s.step(5)
    print(s.state)

    print("STEP 2 (should DENY)")
    s.step(5)
    print(s.state)

    print("WRITE OK")
    s.write_artifact("ok.txt", "hello")

    print("WRITE VIOLATION")
    s.write_artifact("../README.md", "nope")

    print("HISTORY")
    for event in s.state.history:
        print(event)


if __name__ == "__main__":
    main()
