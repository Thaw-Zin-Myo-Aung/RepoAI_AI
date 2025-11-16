package th.ac.mfu.repoai.repository;

import java.util.List;
import java.util.Optional;
import org.springframework.data.repository.CrudRepository;
import th.ac.mfu.repoai.domain.Repository;
import th.ac.mfu.repoai.domain.User;

public interface RepositoryRepository extends CrudRepository<Repository, Long> {
    List<Repository> findAllBy();

    List<Repository> findByUser(User user);

    Optional<Repository> findByFullName(String fullName);

    Optional<Repository> findByOwnerAndName(String owner, String name);
}
