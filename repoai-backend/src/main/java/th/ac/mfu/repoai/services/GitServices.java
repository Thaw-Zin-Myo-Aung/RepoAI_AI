package th.ac.mfu.repoai.services;

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.client.HttpStatusCodeException;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

import th.ac.mfu.repoai.domain.BranchPushRequest;
import th.ac.mfu.repoai.domain.Repository;
import th.ac.mfu.repoai.domain.User;

import th.ac.mfu.repoai.domain.branchdto.BranchSummary;
import th.ac.mfu.repoai.domain.repositorydto.RepositoryDto;
import th.ac.mfu.repoai.repository.RepositoryRepository;
import th.ac.mfu.repoai.repository.UserRepository;

import org.springframework.security.core.Authentication;
import org.springframework.http.*;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClientService;
import org.springframework.security.oauth2.core.OAuth2AccessToken;
import org.springframework.http.client.HttpComponentsClientHttpRequestFactory;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class GitServices {

    private final OAuth2AuthorizedClientService authorizedClientService;
    private OAuth2AccessToken token; // Store token here
    private final RepositoryRepository repositoryRepository;
    private final UserRepository userRepository;

    public GitServices(OAuth2AuthorizedClientService authorizedClientService,
            RepositoryRepository repositoryRepository,
            UserRepository userRepository) {
        this.authorizedClientService = authorizedClientService;
        this.repositoryRepository = repositoryRepository;
        this.userRepository = userRepository;
    }

    /**
     * Load GitHub OAuth2 access token for the logged-in user
     */
    public ResponseEntity<OAuth2AccessToken> loadGitHubToken(Authentication principal) {
        String clientRegistrationId = "github";
        if (principal == null) {
            // No authenticated principal in the context
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(null);
        }

        OAuth2AuthorizedClient client = authorizedClientService
                .loadAuthorizedClient(clientRegistrationId, principal.getName());

        if (client == null || client.getAccessToken() == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(null);
        }

        this.token = client.getAccessToken(); // Save token for future use
        return ResponseEntity.ok(token);
    }

    /**
     * Generic method to call GitHub API using the stored token
     */
    public ResponseEntity<String> callGitHubApi(String url) {
        if (token == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body("GitHub token not loaded, please login");
        }

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setBearerAuth(token.getTokenValue());
            headers.set("Accept", "application/vnd.github+json");
            headers.set("X-GitHub-Api-Version", "2022-11-28");
            HttpEntity<Void> entity = new HttpEntity<>(headers);

            RestTemplate restTemplate = buildPatchCapableRestTemplate();
            ResponseEntity<String> response = restTemplate.exchange(
                    url,
                    HttpMethod.GET,
                    entity,
                    String.class);

            if (response.getStatusCode() == HttpStatus.UNAUTHORIZED) {
                this.token = null; // clear token locally
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body("GitHub token expired or revoked, please login again");
            }

            return ResponseEntity.status(response.getStatusCode()).body(response.getBody());
        } catch (HttpStatusCodeException e) {
            // Pass through GitHub's actual status and response body instead of 500
            if (e.getStatusCode() == HttpStatus.UNAUTHORIZED) {
                this.token = null;
            }
            return ResponseEntity.status(e.getStatusCode()).body(e.getResponseBodyAsString());
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("GitHub API call failed: " + e.getMessage());
        }
    }

    /**
     * Generic method to call GitHub API with method + JSON body
     */
    private ResponseEntity<String> callGitHubApi(String url, HttpMethod method, Object body) {
        if (token == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body("GitHub token not loaded, please login");
        }

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setBearerAuth(token.getTokenValue());
            headers.set("Accept", "application/vnd.github+json");
            headers.set("X-GitHub-Api-Version", "2022-11-28");
            headers.setContentType(MediaType.APPLICATION_JSON);

            HttpEntity<Object> entity = new HttpEntity<>(body, headers);

            RestTemplate restTemplate = buildPatchCapableRestTemplate();
            ResponseEntity<String> response = restTemplate.exchange(
                    url,
                    method,
                    entity,
                    String.class);

            if (response.getStatusCode() == HttpStatus.UNAUTHORIZED) {
                this.token = null; // clear token locally
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body("GitHub token expired or revoked, please login again");
            }

            return ResponseEntity.status(response.getStatusCode()).body(response.getBody());
        } catch (HttpStatusCodeException e) {
            // Pass through GitHub's actual status and response body instead of 500
            if (e.getStatusCode() == HttpStatus.UNAUTHORIZED) {
                this.token = null;
            }
            return ResponseEntity.status(e.getStatusCode()).body(e.getResponseBodyAsString());
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("GitHub API call failed: " + e.getMessage());
        }
    }

    private RestTemplate buildPatchCapableRestTemplate() {
        // Use Apache HttpClient to support HTTP PATCH with RestTemplate
        HttpComponentsClientHttpRequestFactory factory = new HttpComponentsClientHttpRequestFactory();
        return new RestTemplate(factory);
    }

    /**
     * Example: get /user info
     */
    public ResponseEntity<Map<String, Object>> getUserInfo() {
        ResponseEntity<String> response = callGitHubApi("https://api.github.com/user");

        if (!response.getStatusCode().is2xxSuccessful()) {
            return ResponseEntity.status(response.getStatusCode())
                    .body(Map.of("error", response.getBody()));
        }

        try {
            ObjectMapper mapper = new ObjectMapper();
            Map<String, Object> userInfo = mapper.readValue(
                    response.getBody(),
                    new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {
                    });

            // If email is null, fetch /user/emails
            if (userInfo.get("email") == null) {
                ResponseEntity<String> emailsResponse = callGitHubApi("https://api.github.com/user/emails");

                if (emailsResponse.getStatusCode().is2xxSuccessful()) {
                    List<Map<String, Object>> emails = mapper.readValue(
                            emailsResponse.getBody(),
                            new com.fasterxml.jackson.core.type.TypeReference<List<Map<String, Object>>>() {
                            });
                    String primaryEmail = emails.stream()
                            .filter(e -> Boolean.TRUE.equals(e.get("primary"))
                                    && Boolean.TRUE.equals(e.get("verified")))
                            .map(e -> (String) e.get("email"))
                            .findFirst()
                            .orElse(null);
                    userInfo.put("email", primaryEmail);
                }
            }

            return ResponseEntity.ok(userInfo);

        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Failed to parse GitHub response: " + e.getMessage()));
        }
    }

    public ResponseEntity<List<Map<String, Object>>> getUserRepositories() {
        ResponseEntity<String> response = callGitHubApi("https://api.github.com/user/repos");

        if (!response.getStatusCode().is2xxSuccessful()) {
            return ResponseEntity.status(response.getStatusCode())
                    .body(List.of(Map.of("error", response.getBody())));
        }

        try {
            ObjectMapper mapper = new ObjectMapper();
            mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

            List<Map<String, Object>> repositories = mapper.readValue(
                    response.getBody(),
                    new TypeReference<List<Map<String, Object>>>() {
                    });

            List<Map<String, Object>> simplifiedRepos = new ArrayList<>();
                    
            for (Map<String, Object> repo : repositories) {
                Map<?, ?> owner = null;
                Object ownerObj = repo.get("owner");
                if (ownerObj instanceof Map<?, ?> m) {
                    owner = m;
                }
                System.out.println(repo.keySet().toString());
                System.out.println(repo.get("language"));
                System.out.println(repo.get("languages_url"));
                System.out.println(repo.get("size"));
                Long repoId = ((Number) repo.get("id")).longValue();
                String repoName = (String) repo.get("name");
                String fullName = (String) repo.get("full_name");
                String htmlUrl = (String) repo.get("html_url");
                String description = (String) repo.get("description");
                String defaultBranch = (String) repo.get("default_branch");
                Boolean isPrivateObj = (Boolean) repo.get("private");
                boolean isPrivate = isPrivateObj != null ? isPrivateObj : false;
                String ownerLogin = owner != null ? (String) owner.get("login") : null;
                Long ownerGithubId = owner != null ? ((Number) owner.get("id")).longValue() : null;

                User user = userRepository.findByGithubId(ownerGithubId)
                        .orElse(null);

                Repository entity = repositoryRepository.findById(repoId)
                        .orElse(new Repository());

                entity.setRepoId(repoId);
                entity.setOwner(ownerLogin);
                entity.setPrivate(isPrivate);
                entity.setFullName(fullName);
                entity.setHtmlUrl(htmlUrl);
                entity.setName(repoName);
                entity.setDescription(description);
                entity.setDefaultBranch(defaultBranch);
                entity.setOwnerGithubId(ownerGithubId);
                entity.setUser(user);

                repositoryRepository.save(entity);

                // Prepare frontend-friendly response (null-safe)
                java.util.Map<String, Object> repoSummary = new java.util.LinkedHashMap<>();
                repoSummary.put("name", repoName);
                repoSummary.put("repo_id", repoId);
                repoSummary.put("full_name", fullName);
                repoSummary.put("html_url", htmlUrl);
                repoSummary.put("description", description); // may be null and that's okay
                repoSummary.put("default_branch", defaultBranch); // may be null
                repoSummary.put("private", isPrivate);
                repoSummary.put("owner", ownerLogin); // may be null for org-owned repos
                repoSummary.put("owner_github_id", ownerGithubId); // may be null
                simplifiedRepos.add(repoSummary);
            }

            // ✅ Optional: clean up DB (delete repos not in GitHub anymore)
            cleanOldRepos(simplifiedRepos);

            return ResponseEntity.ok(simplifiedRepos);

        } catch (Exception e) {
            e.printStackTrace();
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(List.of(Map.of("error", "Failed to parse repositories: " + e.getMessage())));
        }
    }

    // =============================
    // Repository Management (GitHub)
    // =============================

    /**
     * Create a repository under the authenticated user.
     * Required: name
     * Optional: description, private, default_branch, auto_init
     * Docs:
     * https://docs.github.com/en/rest/repos/repos#create-a-repository-for-the-authenticated-user
     */
    public ResponseEntity<Map<String, Object>> createUserRepository(
            String name,
            String description,
            Boolean isPrivate,
            String defaultBranch,
            Boolean autoInit) {
        if (name == null || name.isBlank()) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("error", "name is required"));
        }

        Map<String, Object> payload = new java.util.LinkedHashMap<>();
        payload.put("name", name);
        if (description != null)
            payload.put("description", description);
        if (isPrivate != null)
            payload.put("private", isPrivate);
        if (defaultBranch != null)
            payload.put("default_branch", defaultBranch);
        if (autoInit != null)
            payload.put("auto_init", autoInit);

        ResponseEntity<String> response = callGitHubApi(
                "https://api.github.com/user/repos",
                HttpMethod.POST,
                payload);

        if (!response.getStatusCode().is2xxSuccessful()) {
            return ResponseEntity.status(response.getStatusCode())
                    .body(Map.of("error", response.getBody()));
        }

        try {
            ObjectMapper mapper = new ObjectMapper();
            Map<String, Object> body = mapper.readValue(
                    response.getBody(),
                    new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {
                    });
            return ResponseEntity.status(HttpStatus.CREATED).body(body);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Failed to parse create repo response: " + e.getMessage()));
        }
    }

    /**
     * Update a repository by owner/name
     * Docs: https://docs.github.com/en/rest/repos/repos#update-a-repository
     */
    public ResponseEntity<Map<String, Object>> updateRepository(
            String owner,
            String repo,
            Map<String, Object> updates) {
        if (owner == null || owner.isBlank() || repo == null || repo.isBlank()) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("error", "owner and repo are required"));
        }
        if (updates == null || updates.isEmpty()) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("error", "updates body is required"));
        }

        String url = String.format("https://api.github.com/repos/%s/%s", owner, repo);
        ResponseEntity<String> response = callGitHubApi(url, HttpMethod.PATCH, updates);
        if (!response.getStatusCode().is2xxSuccessful()) {
            return ResponseEntity.status(response.getStatusCode())
                    .body(Map.of("error", response.getBody()));
        }

        try {
            ObjectMapper mapper = new ObjectMapper();
            Map<String, Object> body = mapper.readValue(
                    response.getBody(),
                    new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {
                    });
            return ResponseEntity.ok(body);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Failed to parse update repo response: " + e.getMessage()));
        }
    }

    /**
     * Delete a repository by owner/name
     * Docs: https://docs.github.com/en/rest/repos/repos#delete-a-repository
     */
    public ResponseEntity<String> deleteRepository(String owner, String repo) {
        if (owner == null || owner.isBlank() || repo == null || repo.isBlank()) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body("owner and repo are required");
        }
        String url = String.format("https://api.github.com/repos/%s/%s", owner, repo);
        ResponseEntity<String> response = callGitHubApi(url, HttpMethod.DELETE, null);
        if (response.getStatusCode().is2xxSuccessful() || response.getStatusCode() == HttpStatus.NO_CONTENT) {
            return ResponseEntity.noContent().build();
        }
        return ResponseEntity.status(response.getStatusCode()).body(response.getBody());
    }

    // ==============================================
    // GitHub Operations + Local Database Synchronize
    // ==============================================

    public ResponseEntity<RepositoryDto> createUserRepositoryAndSave(
            String name,
            String description,
            Boolean isPrivate,
            String defaultBranch,
            Boolean autoInit) {
        ResponseEntity<Map<String, Object>> gh = createUserRepository(name, description, isPrivate, defaultBranch,
                autoInit);
        if (!gh.getStatusCode().is2xxSuccessful() || gh.getBody() == null) {
            return ResponseEntity.status(gh.getStatusCode()).build();
        }
        Map<String, Object> repoJson = gh.getBody();
        Repository entity = upsertRepositoryFromGitHubJson(repoJson);
        return ResponseEntity.status(HttpStatus.CREATED).body(RepositoryDto.fromEntity(entity));
    }

    public ResponseEntity<RepositoryDto> updateRepositoryAndSave(String owner, String repo,
            Map<String, Object> updates) {
        ResponseEntity<Map<String, Object>> gh = updateRepository(owner, repo, updates);
        if (!gh.getStatusCode().is2xxSuccessful() || gh.getBody() == null) {
            return ResponseEntity.status(gh.getStatusCode()).build();
        }
        Map<String, Object> repoJson = gh.getBody();
        Repository entity = upsertRepositoryFromGitHubJson(repoJson);
        return ResponseEntity.ok(RepositoryDto.fromEntity(entity));
    }

    public ResponseEntity<Void> deleteRepositoryAndRemove(String owner, String repo) {
        ResponseEntity<String> gh = deleteRepository(owner, repo);
        if (gh.getStatusCode().is2xxSuccessful() || gh.getStatusCode() == HttpStatus.NO_CONTENT) {
            // Try to remove local record by owner+name
            repositoryRepository.findByOwnerAndName(owner, repo)
                    .ifPresent(repositoryRepository::delete);
            return ResponseEntity.noContent().build();
        }
        return ResponseEntity.status(gh.getStatusCode()).build();
    }

    private Repository upsertRepositoryFromGitHubJson(Map<String, Object> repoJson) {
        Long repoId = ((Number) repoJson.get("id")).longValue();
        String name = (String) repoJson.get("name");
        String fullName = (String) repoJson.get("full_name");
        String htmlUrl = (String) repoJson.get("html_url");
        String description = (String) repoJson.get("description");
        String defaultBranch = (String) repoJson.get("default_branch");
        Boolean isPrivateObj = (Boolean) repoJson.get("private");
        boolean isPrivate = isPrivateObj != null ? isPrivateObj : false;

        Map<?, ?> owner = null;
        Object ownerObj = repoJson.get("owner");
        if (ownerObj instanceof Map<?, ?> m)
            owner = m;
        String ownerLogin = owner != null ? (String) owner.get("login") : null;
        Long ownerGithubId = owner != null && owner.get("id") != null ? ((Number) owner.get("id")).longValue() : null;

        User user = ownerGithubId != null ? userRepository.findByGithubId(ownerGithubId).orElse(null) : null;

        Repository entity = repositoryRepository.findById(repoId).orElse(new Repository());
        entity.setRepoId(repoId);
        entity.setOwner(ownerLogin);
        entity.setPrivate(isPrivate);
        entity.setFullName(fullName);
        entity.setHtmlUrl(htmlUrl);
        entity.setName(name);
        entity.setDescription(description);
        entity.setDefaultBranch(defaultBranch);
        entity.setOwnerGithubId(ownerGithubId);
        entity.setUser(user);

        return repositoryRepository.save(entity);
    }

    private void cleanOldRepos(List<Map<String, Object>> currentRepos) {
        List<Long> currentRepoIds = currentRepos.stream()
                .map(r -> ((Number) r.get("repo_id")).longValue())
                .toList();

        List<Repository> allRepos = repositoryRepository.findAllBy();

        for (Repository repo : allRepos) {
            if (!currentRepoIds.contains(repo.getRepoId())) {
                repositoryRepository.delete(repo);
            }
        }
    }

    public List<BranchSummary> listBranches(
            Authentication auth,
            String owner,
            String repo,
            Boolean protectedOnly,
            int page,
            int perPage) {

        String url = String.format(
                "https://api.github.com/repos/%s/%s/branches?page=%d&per_page=%d%s",
                owner, repo, page, perPage,
                protectedOnly == null ? "" : "&protected=" + protectedOnly);

        var resp = callGitHubApi(url); // uses cached token/headers
        if (!resp.getStatusCode().is2xxSuccessful()) {
            // propagate GitHub’s status instead of 500
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.valueOf(resp.getStatusCode().value()),
                    "GitHub list branches failed: " + resp.getBody());
        }

        try {
            var mapper = new ObjectMapper()
                    .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

            // Option 1: TypeFactory (no overload ambiguity)
            var listType = mapper.getTypeFactory()
                    .constructCollectionType(java.util.List.class, BranchSummary.class);
            return mapper.readValue(resp.getBody(), listType);

            // Option 2: TypeReference (also fine if imports are correct)
            // return mapper.readValue(resp.getBody(), new
            // TypeReference<List<BranchSummary>>() {});
        } catch (Exception e) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.BAD_GATEWAY,
                    "Cannot parse GitHub branches JSON", e);
        }
    }

    public String getBranchSha(String owner, String repo, String baseBranch, String token) {

        String url = String.format("https://api.github.com/repos/%s/%s/branches/%s", owner, repo, baseBranch);

        RestTemplate rest = new RestTemplate();

        HttpHeaders headers = new HttpHeaders();

        headers.set("Authorization", "Bearer " + token);

        HttpEntity<?> entity = new HttpEntity<>(headers);

        ResponseEntity<Map> response = rest.exchange(url, HttpMethod.GET, entity, Map.class);

        Map commit = (Map) response.getBody().get("commit");

        return (String) commit.get("sha");
    }

    public void createBranch(String owner, String repo, String newBranch, String sha, String token) {
        String url = String.format("https://api.github.com/repos/%s/%s/git/refs", owner, repo);
        RestTemplate rest = new RestTemplate();
        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + token);
        headers.setContentType(MediaType.APPLICATION_JSON);
        Map<String, Object> body = new HashMap<>();
        body.put("ref", "refs/heads/" + newBranch);
        body.put("sha", sha);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);
        rest.postForEntity(url, entity, String.class);
    }

    public void putFile(String owner, String repo, BranchPushRequest.FileChange file, String message, String branch,
            String token) {
        String url = String.format("https://api.github.com/repos/%s/%s/contents/%s", owner, repo, file.path);
        RestTemplate rest = new RestTemplate();
        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + token);
        headers.setContentType(MediaType.APPLICATION_JSON);
        Map<String, Object> body = new HashMap<>();
        body.put("message", message);
        body.put("content", file.base64Content);
        body.put("branch", branch);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);
        rest.exchange(url, HttpMethod.PUT, entity, Map.class);
    }

}