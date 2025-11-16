package th.ac.mfu.repoai.controllers;

import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.core.OAuth2AccessToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import th.ac.mfu.repoai.repository.UserRepository;
import th.ac.mfu.repoai.services.GitServices;

@RestController
@RequestMapping("/api/user")
public class UserController {

	@Autowired
	private GitServices gitServices;

	@Autowired
	private UserRepository userRepository;

	// Return the authenticated user's GitHub profile (login, id, email, avatar, etc.)
	@GetMapping("/profile")
	public ResponseEntity<?> getUserProfile(Authentication principal) {
		ResponseEntity<OAuth2AccessToken> tokenResp = gitServices.loadGitHubToken(principal);
		if (!tokenResp.getStatusCode().is2xxSuccessful() || tokenResp.getBody() == null) {
			return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
					.body(Map.of("error", "Not authenticated"));
		}

		ResponseEntity<Map<String, Object>> userInfoResponse = gitServices.getUserInfo();
		if (!userInfoResponse.getStatusCode().is2xxSuccessful() || userInfoResponse.getBody() == null) {
			return ResponseEntity.status(userInfoResponse.getStatusCode())
					.body(userInfoResponse.getBody());
		}

		Map<String, Object> info = userInfoResponse.getBody();
		Object idObj = info != null ? info.get("id") : null;
		if (!(idObj instanceof Number)) {
			return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
					.body(Map.of("error", "GitHub user id missing in response"));
		}
		Long githubId = ((Number) idObj).longValue();

		return userRepository.findByGithubId(githubId)
				.<ResponseEntity<?>>map(ResponseEntity::ok)
				.orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND)
						.body(Map.of("error", "User not found in database")));
	}
}
