package th.ac.mfu.repoai.controllers;

import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.core.OAuth2AccessToken;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.security.web.authentication.logout.SecurityContextLogoutHandler;

import java.time.Duration;
import org.springframework.http.ResponseCookie;

import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import th.ac.mfu.repoai.domain.User;
import th.ac.mfu.repoai.repository.UserRepository;
import th.ac.mfu.repoai.services.GitServices;

@Controller
@RequestMapping("/api/auth")
public class AuthController {

    @Autowired
    private GitServices gitServices;

    @Autowired
    private UserRepository userRepository;

    @Value("${app.frontend.url:http://localhost:5173}")
    private String frontendUrl;

    // Helper method to detect if we're on HTTPS
    private boolean isSecureRequest(HttpServletRequest request) {
        // Check if running on Cloud Run or other HTTPS environment
        String proto = request.getHeader("X-Forwarded-Proto");
        return "https".equalsIgnoreCase(proto) || request.isSecure();
    }

    @GetMapping("/token")
    @ResponseBody
    public ResponseEntity<String> token(Authentication principal) {
        ResponseEntity<OAuth2AccessToken> response = gitServices.loadGitHubToken(principal);

        if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body("Not authenticated");
        }
        OAuth2AccessToken token = response.getBody();
        if (token == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body("Not authenticated");
        }
        return ResponseEntity.ok(token.getTokenValue());
    }

    @GetMapping("/login")
    public void login(Authentication principal, HttpServletResponse response) throws IOException {
        if (principal == null) {
            // If not authenticated yet, start the OAuth2 flow
            response.sendRedirect("/oauth2/authorization/github");
            return;
        }

        // Get user info from GitHub (includes email handling)
        ResponseEntity<OAuth2AccessToken> tokenResp = gitServices.loadGitHubToken(principal);
        if (!tokenResp.getStatusCode().is2xxSuccessful() || tokenResp.getBody() == null) {
            response.sendRedirect("https://repoai-frontend-516479753863.us-central1.run.app/login?error=unauthorized");
            return;
        }

        ResponseEntity<Map<String, Object>> userInfoResponse = gitServices.getUserInfo();

        if (!userInfoResponse.getStatusCode().is2xxSuccessful() || userInfoResponse.getBody() == null) {
            response.sendRedirect("https://repoai-frontend-516479753863.us-central1.run.app/login?error=unauthorized");
            return;
        }

        Map<String, Object> attributes = userInfoResponse.getBody();
        if (attributes == null) {
            response.sendRedirect("https://repoai-frontend-516479753863.us-central1.run.app/login?error=unauthorized");
            return;
        }

        Long githubId = ((Number) attributes.get("id")).longValue();
        String username = (String) attributes.get("login");
        String email = (String) attributes.get("email");
        String avatarUrl = (String) attributes.get("avatar_url");
        String profileUrl = (String) attributes.get("html_url");

        User user = userRepository.findByGithubId(githubId).orElseGet(() -> {
            User newUser = new User();
            newUser.setGithubId(githubId);
            newUser.setUsername(username);
            newUser.setEmail(email);
            newUser.setAvatarUrl(avatarUrl);
            newUser.setProfileUrl(profileUrl);
            return userRepository.save(newUser);
        });

        // Save user and redirect to frontend home
        System.out.println("User logged in: " + user.getUsername());
        response.sendRedirect("https://repoai-frontend-516479753863.us-central1.run.app/home");
    }

    // Start OAuth and remember where to send the user back on success
    @GetMapping("/start")
    public ResponseEntity<Void> start(
            @org.springframework.web.bind.annotation.RequestParam(required = false) String redirect,
            HttpServletRequest request) {
        String target = (redirect == null || redirect.isBlank()) ? frontendUrl : redirect;
        boolean isHttps = isSecureRequest(request);

        ResponseCookie cookie = ResponseCookie.from("app_redirect",
                URLEncoder.encode(target, StandardCharsets.UTF_8))
                .httpOnly(true)
                .secure(isHttps) // Use helper method
                .sameSite("None") // Changed to None for cross-site
                .path("/")
                .maxAge(Duration.ofMinutes(5))
                .build();

        return ResponseEntity.status(HttpStatus.FOUND)
                .header(HttpHeaders.SET_COOKIE, cookie.toString())
                .header("Location", "/oauth2/authorization/github")
                .build();
    }

    // Explicit endpoint to initiate OAuth2 login from frontends
    @GetMapping("/authorize")
    public ResponseEntity<Void> authorize() {
        return ResponseEntity.status(HttpStatus.FOUND)
                .header("Location", "/oauth2/authorization/github")
                .build();
    }

    // Lightweight status endpoint for SPAs to check auth state
    @GetMapping("/status")
    @ResponseBody
    public ResponseEntity<Map<String, Object>> status(Authentication principal) {
        boolean authenticated = principal != null;
        return ResponseEntity.ok(Map.of(
                "authenticated", authenticated));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request, HttpServletResponse response,
            Authentication authentication) throws ServletException {
        // Invalidate Spring Security session and clear authentication
        new SecurityContextLogoutHandler().logout(request, response, authentication);

        boolean isHttps = isSecureRequest(request);

        // Proactively expire cookies that may exist in browser
        ResponseCookie clearSession = ResponseCookie.from("JSESSIONID", "")
                .httpOnly(true)
                .secure(isHttps)
                .sameSite("None") // Changed to None for cross-site
                .path("/")
                .maxAge(0)
                .build();

        ResponseCookie clearRedirect = ResponseCookie.from("app_redirect", "")
                .httpOnly(true)
                .secure(isHttps)
                .sameSite("None") // Changed to None for cross-site
                .path("/")
                .maxAge(0)
                .build();

        return ResponseEntity.noContent()
                .header(HttpHeaders.SET_COOKIE, clearSession.toString(), clearRedirect.toString())
                .build();
    }
}