# ---- Stage 1 : build du WAR avec Gradle et JDK 21 ----
FROM eclipse-temurin:21-jdk-alpine AS build

WORKDIR /app

# Wrapper Gradle + fichiers de config d'abord (couche cachable)
COPY gradlew .
COPY gradle gradle
COPY build.gradle settings.gradle ./

# Le code source (nécessaire dès la génération OpenAPI au compileJava)
COPY src src

# Build du WAR sans exécuter les tests car probleme lié au nom
# de mon user Windows. Le cache mount accélère les
# builds successifs en conservant le Gradle User Home.
RUN --mount=type=cache,target=/root/.gradle \
    chmod +x gradlew && \
    ./gradlew bootWar -x test --no-daemon

# ---- Stage 2 : image finale, JRE seule (pas de JDK) ----
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# On copie uniquement le WAR produit. Le glob évite de coder en dur
# le numéro de version (0.2.4).
COPY --from=build /app/build/libs/*.war app.war

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.war"]