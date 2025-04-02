dating-server:
	$(TROUPE)/bin/troupec dating-server.trp -o ./out/dating-server.js
	node $(TROUPE)/rt/built/troupe.js -f=./out/dating-server.js --id=../ids/id-server.json --trustmap=../trustmaps/GoT.json --aliases=aliases.json

dating-alice:
	$(TROUPE)/bin/troupec dating-alice.trp -o ./out/dating-alice.js
	node $(TROUPE)/rt/built/troupe.js -f=./out/dating-alice.js --id=../ids/alice.json --trustmap=../trustmaps/alice.json --aliases=aliases.json

dating-bob:
	$(TROUPE)/bin/troupec dating-bob.trp -o ./out/dating-bob.js
	node $(TROUPE)/rt/built/troupe.js -f=./out/dating-bob.js --id=../ids/bob.json --trustmap=../trustmaps/bob.json --aliases=aliases.json

dating-carl:
	$(TROUPE)/bin/troupec dating-carl.trp -o ./out/dating-carl.js
	node $(TROUPE)/rt/built/troupe.js -f=./out/dating-carl.js --id=../ids/carl.json --trustmap=../trustmaps/carl.json --aliases=aliases.json

dating-malicious:
	$(TROUPE)/bin/troupec dating-malicious.trp -o ./out/dating-malicious.js
	node $(TROUPE)/rt/built/troupe.js -f=./out/dating-malicious.js --id=../ids/malicious.json --trustmap=../trustmaps/malicious.json --aliases=aliases.json
