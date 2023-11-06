# Wyoming Handle External

[Wyoming protocol](https://github.com/rhasspy/wyoming) server that runs an external program to handle intents and generate a response.

Input text is sent to the standard input of `--program` and its standard output is sent back as the response in a "handled". If the program's exit code is not 0, a "not handled" event is sent back.


## Example

Run a server that repeats back whatever it was sent:

``` sh
script/run \
  --uri 'tcp://127.0.0.1:10500' \
  --program cat \
  --language en
```
