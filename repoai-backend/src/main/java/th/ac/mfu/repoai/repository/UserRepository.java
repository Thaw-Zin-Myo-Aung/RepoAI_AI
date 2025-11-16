package th.ac.mfu.repoai.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.repository.CrudRepository;

import th.ac.mfu.repoai.domain.User;

public interface UserRepository extends CrudRepository<User, Long> {
    List<User> findAll();
    Optional<User> findByGithubId(Long githubId);
}