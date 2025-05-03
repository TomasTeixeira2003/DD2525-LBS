package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"strings"
)

const fuzzChars = "!@#$%^&*()_+-=[]{}|;:',.<>?/"

var (
	endpoint    string
	gqlFile     string
	wordlistPath string
)

func init() {
	flag.StringVar(&endpoint, "endpoint", "", "URL of the GraphQL endpoint")
	flag.StringVar(&gqlFile, "gqlfile", "", "Path to the GraphQL schema file in JSON format")
	flag.StringVar(&wordlistPath, "wordlist", "", "Path to the wordlist file (optional)")
}

type GraphQLArgument struct {
    Name string         `json:"name"`
    Type GraphQLFieldType `json:"type"`
}

type GraphQLType struct {
    Kind        string             `json:"kind"`
    Name        string             `json:"name"`
    Fields      []GraphQLField     `json:"fields,omitempty"`
    InputFields []GraphQLArgument  `json:"inputFields,omitempty"`
}


type GraphQLField struct {
    Name string             `json:"name"`
    Type GraphQLFieldType   `json:"type"`
    Args []GraphQLArgument  `json:"args,omitempty"`
}

type GraphQLResponse struct {
	Data   interface{} `json:"data"`
	Errors interface{} `json:"errors"`
}

type GraphQLFieldArg struct {
	Name string           `json:"name"`
	Type GraphQLFieldType `json:"type"`
}

type GraphQLFieldType struct {
    Kind   string           `json:"kind"`
    Name   string           `json:"name"`
    OfType *GraphQLFieldType `json:"ofType,omitempty"`
}

type GraphQLRequest struct {
	Query string `json:"query"`
}

func readSchemaFromFile(filePath string) ([]GraphQLType, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("error opening schema file: %w", err)
	}
	defer file.Close()

	bytes, err := ioutil.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("error reading schema file: %w", err)
	}

	var schema struct {
		Data struct {
			Schema struct {
				Types []GraphQLType `json:"types"`
			} `json:"__schema"`
		} `json:"data"`
	}
	if err := json.Unmarshal(bytes, &schema); err != nil {
		return nil, fmt.Errorf("error unmarshalling schema JSON: %w", err)
	}

	return schema.Data.Schema.Types, nil
}

// returns a selection-set string for type t (e.g. "id", or "paste { id }")
// Option A: Scalars only (no recursion) = If you just want any valid field, restrict buildSelection to pick the first scalar it finds
/* func buildSelection(t GraphQLFieldType, types []GraphQLType) string {
    // unwrap
    for t.Kind == "LIST" || t.Kind == "NON_NULL" {
        t = *t.OfType
    }
    // find the matching OBJECT type
    for _, obj := range types {
        if obj.Name == t.Name {
            for _, f := range obj.Fields {
                // unwrap field type
                ft := f.Type
                for ft.Kind == "LIST" || ft.Kind == "NON_NULL" {
                    ft = *ft.OfType
                }
                if ft.Kind == "SCALAR" {
                    return f.Name
                }
            }
        }
    }
    return ""
} */

//Option B: Depth‐limited (track visited) = If you’d like a bit more richness but still guard against loops, pass along a visited set:
func buildSelection(
    t GraphQLFieldType,
    types []GraphQLType,
    visited map[string]bool,
    depth int,
) string {
    if depth > 2 {
        return ""
    }
    // unwrap LIST/NON_NULL
    for t.Kind == "LIST" || t.Kind == "NON_NULL" {
        t = *t.OfType
    }
    // find the matching OBJECT or INPUT_OBJECT
    for _, obj := range types {
        if obj.Name == t.Name {
            if visited[obj.Name] {
                return ""
            }
            visited[obj.Name] = true

            var sels []string
            for _, f := range obj.Fields {
                // unwrap field type
                ft := f.Type
                for ft.Kind == "LIST" || ft.Kind == "NON_NULL" {
                    ft = *ft.OfType
                }
                if ft.Kind == "SCALAR" {
                    // pick scalar directly
                    sels = append(sels, f.Name)
                } else {
                    // recurse for nested object
                    nested := buildSelection(f.Type, types, visited, depth+1)
                    if nested != "" {
                        sels = append(sels, fmt.Sprintf("%s { %s }", f.Name, nested))
                    }
                }
                if len(sels) >= 2 {
                    break
                }
            }
            return strings.Join(sels, " ")
        }
    }
    return ""
}

// pickArgValue renders a fuzzString into a GraphQL literal of the correct kind.
func pickArgValue(arg GraphQLArgument, fuzzString string, types []GraphQLType) string {
    // unwrap to core
    t := arg.Type
    for t.Kind == "NON_NULL" || t.Kind == "LIST" {
        t = *t.OfType
    }

    // if it’s an input object, emit { field: value, ... }
    if t.Kind == "INPUT_OBJECT" {
        // find the GraphQLType entry
        for _, obj := range types {
            if obj.Name == t.Name {
                var parts []string
                for _, in := range obj.InputFields {
                    // all of these are non-null Strings in DVGA
                    parts = append(parts,
                        fmt.Sprintf("%s: %q", in.Name, fuzzString))
                }
                return fmt.Sprintf("%s: { %s }", arg.Name, strings.Join(parts, ", "))
            }
        }
    }

    // otherwise scalar/ID/Boolean/Int
    switch t.Name {
    case "Int":
        return fmt.Sprintf("%s: %d", arg.Name, 0)
    case "Boolean":
        return fmt.Sprintf("%s: %t", arg.Name, false)
    case "String", "ID":
        return fmt.Sprintf("%s: %q", arg.Name, fuzzString)
    default:
        // fallback
        return fmt.Sprintf("%s: \"\"", arg.Name)
    }
}


func fuzzGraphQL(url string, types []GraphQLType, wordlist []string) {
    // 1) Identify the two roots in your schema
    var roots []GraphQLType
    for _, t := range types {
        if t.Kind == "OBJECT" && (t.Name == "Query" || t.Name == "Mutations") {
            roots = append(roots, t)
        }
    }

    for _, root := range roots {
        // 2) Decide GraphQL operation keyword
        op := "query"
        if root.Name == "Mutations" {
            op = "mutation"
        }

        for _, field := range root.Fields {
            // 3) Build your fuzz payload list
            fuzzList := []string{""}
            if len(wordlist) > 0 {
                fuzzList = wordlist
            }

            for _, fuzzString := range fuzzList {
                // 4) Render args with type-correct literals
                // in your fuzz loop:
				var args []string
				for _, arg := range field.Args {
					args = append(args, pickArgValue(arg, fuzzString, types))
				}
				arglist := strings.Join(args, ", ")

                // 5) Build the nested selection-set
                //For Option A: sel := buildSelection(field.Type, types)
				// FOR OPTION B do the following call instead of teh above:
				sel := buildSelection(field.Type, types, map[string]bool{}, 0)


                // 6) Build final query text
                var q string
                if sel == "" {
                    // scalar return → no selection‐set
                    if arglist != "" {
                        q = fmt.Sprintf("%s { %s(%s) }", op, field.Name, arglist)
                    } else {
                        q = fmt.Sprintf("%s { %s }", op, field.Name)
                    }
                } else {
                    // object return → wrap nested selection
                    if arglist != "" {
                        q = fmt.Sprintf("%s { %s(%s) { %s } }", op, field.Name, arglist, sel)
                    } else {
                        q = fmt.Sprintf("%s { %s { %s } }", op, field.Name, sel)
                    }
                }

                // 7) Send it off
                resp, err := sendQuery(url, q)
                if err != nil {
                    fmt.Println("Error:", err)
                } else {
                    fmt.Printf("Fuzzed Query: %s\nResponse: %v\n", q, resp)
                }
            }
        }
    }
}


func sendQuery(url, query string) (*GraphQLResponse, error) {
		requestBody, err := json.Marshal(GraphQLRequest{Query: query})
	if err != nil {
		return nil, fmt.Errorf("error marshaling request: %w", err)
	}

	// Send the request to the GraphQL endpoint
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(requestBody))
	if err != nil {
		return nil, fmt.Errorf("error sending request: %w", err)
	}
	defer resp.Body.Close()

	
	responseBody, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading response body: %w", err)
	}

	var graphQLResponse GraphQLResponse
	if err := json.Unmarshal(responseBody, &graphQLResponse); err != nil {
		return nil, fmt.Errorf("error unmarshalling response: %w", err)
	}

	return &graphQLResponse, nil
}

func readWordlist(filePath string) ([]string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("error opening wordlist file: %w", err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	var wordlist []string
	for scanner.Scan() {
		wordlist = append(wordlist, scanner.Text())
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error reading wordlist: %w", err)
	}

	return wordlist, nil
}

func main() {
	flag.Parse()

	if endpoint == "" || gqlFile == "" {
		fmt.Println("Both --endpoint and --gqlfile flags are required.")
		flag.Usage()
		return
	}

	var wordlist []string
	if wordlistPath != "" {
		wordlistData, err := readWordlist(wordlistPath)
		if err != nil {
			fmt.Printf("Error reading wordlist: %v\n", err)
			return
		}
		wordlist = wordlistData
	}

	types, err := readSchemaFromFile(gqlFile)
	if err != nil {
		fmt.Printf("Error reading schema file: %v\n", err)
		return
	}

	fuzzGraphQL(endpoint, types, wordlist)
}
