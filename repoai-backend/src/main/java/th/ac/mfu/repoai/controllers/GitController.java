package th.ac.mfu.repoai.controllers;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import th.ac.mfu.repoai.services.GitServices;

@RestController
@RequestMapping("/api/github")
public class GitController {
    private final GitServices gitServices;

    public GitController(GitServices gitServices) {
        this.gitServices = gitServices;
    }

    @GetMapping("/sync_repos")
    public ResponseEntity<?> getUserRepos() {
        return gitServices.getUserRepositories();
    }
}
