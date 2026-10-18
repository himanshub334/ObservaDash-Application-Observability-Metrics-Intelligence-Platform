FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod main.go main_test.go ./
RUN go test ./... && CGO_ENABLED=0 go build -o /collector .
FROM alpine:3.20
RUN adduser -D -H collector
USER collector
COPY --from=build /collector /usr/local/bin/collector
ENTRYPOINT ["/usr/local/bin/collector"]
