FROM eclipse-temurin:21-jre
COPY target/meter-service-*.jar /app/app.jar
USER 10001
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
